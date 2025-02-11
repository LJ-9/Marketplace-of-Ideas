""" Modified to separate model and utils"""
##################################################################
# Code to (re)produce results in the paper 
# "Manipulating the Online Marketplace of Ideas" 
# by Xiaodan Lou, Alessandro Flammini, and Filippo Menczer
# https://arxiv.org/abs/1907.06130
# 
# Notes:
# * Need Python 3.6 or later; eg: `module load python/3.6.6`
# * remember link direction is following, opposite of info spread!
##################################################################

from utils import *
import networkx as nx
import random
import numpy as np
import math
import statistics
import csv
import matplotlib.pyplot as plt
from operator import itemgetter
import sys
import fcntl
import time
from profileit import profile
from graphutils import *
import model 

# create a network with random-walk growth model
# default p = 0.5 for network clustering
# default k_out = 3 is average no. friends within humans & bots
#

def random_walk_network(net_size, p=0.5, k_out=3,seed=100):
  if net_size <= k_out + 1: # if super small just return a clique
    return nx.complete_graph(net_size, create_using=nx.DiGraph())
  G = nx.complete_graph(k_out, create_using=nx.DiGraph()) 
  random.seed(seed)
  for n in range(k_out, net_size):
    target = random.choice(list(G.nodes()))
    friends = [target]
    n_random_friends = 0
    for _ in range(k_out - 1):
      if random.random() < p:
        n_random_friends += 1
    friends.extend(random.sample(list(G.successors(target)), n_random_friends))
    friends.extend(random.sample(list(G.nodes()), k_out - 1 - n_random_friends))
    G.add_node(n)
    for f in friends:
      G.add_edge(n, f)
  return G

# create network of humans and bots
# preferential_targeting is a flag; if False, random targeting
# default n_humans=1000 but 10k for paper
# default beta=0.1 is bots/humans ratio
# default gamma=0.1 is infiltration: probability that a human follows each bot
#
@profile
def init_net(preferential_targeting, verbose=False, targeting_criterion = 'hubs', human_network = None, n_humans=1000, beta=0.1, gamma=0.1):

  # humans
  if human_network is None:
    if verbose: print('Generating human network...')
    H = random_walk_network(n_humans)
  else:
    if verbose: print('Reading human network...')
    H = read_empirical_network(human_network, add_feed=False)
    n_humans = H.number_of_nodes()
  for h in H.nodes:
      #h['bot'] = False #b
    H.nodes[h]['bot'] = False

  # bots
  if verbose: print('Generating bot network...')
  n_bots = int(n_humans * beta) 
  B = random_walk_network(n_bots, seed=101)
  for b in B.nodes:
    B.nodes[b]['bot'] = True

  # merge and add feed
  # feed is array of (quality, fitness, ID) tuples
  if verbose: print('Merging human and bot networks...')
  G = nx.disjoint_union(H, B)
  assert(G.number_of_nodes() == n_humans + n_bots)
  humans = []
  bots = []
  for n in G.nodes:
      #b:initialize feed
    G.nodes[n]['feed'] = []
    #b:now nodes are reindex so we want to keep track of which ones are bots and which are humans
    if G.nodes[n]['bot']:
      bots.append(n)
    else:
      humans.append(n)

  # humans follow bots
  if verbose: print('Humans following bots...')
  if preferential_targeting:
    if targeting_criterion == 'hubs':
      w = [G.in_degree(h) for h in humans]
    elif targeting_criterion == 'partisanship':
      w = [abs(float(G.nodes[h]['party'])) for h in humans]
    elif targeting_criterion == 'misinformation':
      w = [float(G.nodes[h]['misinfo']) for h in humans]
    elif targeting_criterion == 'conservative':
      w = [1 if float(G.nodes[h]['party']) > 0 else 0 for h in humans]
    elif targeting_criterion == 'liberal':
      w = [1 if float(G.nodes[h]['party']) < 0 else 0 for h in humans]
    else:
      raise ValueError('Unrecognized targeting_criterion passed to init_net')
  
  random.seed(102)
  for b in bots:
    n_followers = 0
    for _ in humans:
      if random.random() < gamma:
        n_followers += 1
    if preferential_targeting:
      followers = sample_with_prob_without_replacement(humans, n_followers, w)
    else:
      followers = random.sample(humans, n_followers)
    for f in followers:
      G.add_edge(f, b)
 
  return G


# return (quality, fitness, id) meme tuple depending on bot flag
# using https://en.wikipedia.org/wiki/Inverse_transform_sampling
# default phi = 1 is bot deception; >= 1: meme fitness higher than quality 
# N.B. get_meme.id is an attribute that works as a static var to get unique IDs
#
def get_meme(bot_flag, phi=1):
  if bot_flag:
    exponent = 1 + (1 / phi)
  else:
    exponent = 1 + phi
  u = random.random()
  fitness = 1 - (1 - u)**(1 / exponent)
  if bot_flag:
    quality = 0
  else:
    quality = fitness
  if hasattr(get_meme, 'id'):
    get_meme.id += 1
  else:
    get_meme.id = 0
  return (quality, fitness, get_meme.id)


# count the number of forgotten memes as a function of in_degree (followers)
# using dict attribute 'forgotten_memes' as a static variable
# that can be accessed as: forgotten_memes_per_degree.forgotten_memes
#
# b: seems to only be used for debugging
def forgotten_memes_per_degree(n_forgotten, followers):
  if not hasattr(forgotten_memes_per_degree, 'forgotten_memes'):
    forgotten_memes_per_degree.forgotten_memes = {} # initialize
  if followers in forgotten_memes_per_degree.forgotten_memes:
    forgotten_memes_per_degree.forgotten_memes[followers] += n_forgotten
  else:
    forgotten_memes_per_degree.forgotten_memes[followers] = n_forgotten


# track number of tweets and retweets of each meme
# using dict attribute 'popularity' as a static variable 
# that can be accessed as: track_memes.popularity and
# has prototype {(meme_tuple): popularity}
#
# in addition if quality == 0 we also track the popularity
# by bots and humans separately using another dict attribute 
# track_memes.bad_popularity as a static variable 
# with prototype {"meme_id": [human_popularity, bot_popularity]}
#
def track_memes(meme, bot_flag, theta=1):
  copies = theta if bot_flag else 1
  if not hasattr(track_memes, 'popularity'):
    track_memes.popularity = {}
  if meme in track_memes.popularity:
    track_memes.popularity[meme] += copies
  else:
    track_memes.popularity[meme] = copies
  if meme[0] == 0:
    if not hasattr(track_memes, 'bad_popularity'):
      track_memes.bad_popularity = {}
    oneifbot = 1 if bot_flag else 0
    if meme[2] in track_memes.bad_popularity:
      track_memes.bad_popularity[meme[2]][oneifbot] += copies
    else:
      track_memes.bad_popularity[meme[2]] = [0,0]
      track_memes.bad_popularity[meme[2]][oneifbot] = copies


# a single simulation step in which one agent is activated
# default alpha = 15 is depth of feed
# default mu = 0.75 is average prob of new meme vs retweet; 
#         mu could also be drawn from empirical distribution
#

def simulation_step(G,
                    count_forgotten_memes=False,
                    track_meme=False,
                    alpha=15,
                    mu=0.75,
                    phi=1,
                    theta=1,
                    debug=False):

  agent = random.choice(list(G.nodes()))
  memes_in_feed = G.nodes[agent]['feed']
  
  # tweet or retweet
  if len(memes_in_feed) and random.random() > mu:
    # retweet a meme from feed selected on basis of its fitness
    fitnesses = [m[1] for m in memes_in_feed]
    meme = random.choices(memes_in_feed, weights=fitnesses, k=1)[0]
  else:
    # new meme
    meme = get_meme(G.nodes[agent]['bot'], phi)
  
  # bookkeeping
  if track_meme:
    track_memes(meme, G.nodes[agent]['bot'], theta)

  # spread (truncate feeds at max len alpha)
  followers = G.predecessors(agent)
  # b: count total memes in system
  count = 0
  for f in followers:
      # print('follower feed before:', ["{0:.2f}".format(round(m[0], 2)) for m in G.nodes[f]['feed']])
      # add meme to top of follower's feed (theta copies if poster is bot to simulate flooding)
      if G.nodes[agent]["bot"]:
          G.nodes[f]["feed"][0:0] = [meme] * theta
          count += theta  # b
      else:
          G.nodes[f]["feed"].insert(0, meme)
          count += 1

      # truncate feeds if needed
      if len(G.nodes[f]["feed"]) > alpha:
          if count_forgotten_memes and G.nodes[f]["bot"] == False:
              # count only forgotten memes with zero quality
              forgotten_zeros = 0
              for m in G.nodes[f]["feed"][alpha:]:
                  if m[0] == 0:
                      forgotten_zeros += 1
              forgotten_memes_per_degree(forgotten_zeros, G.in_degree(f))
          del G.nodes[f]["feed"][alpha:]
          # print('follower feed after :', ["{0:.2f}".format(round(m[0], 2)) for m in G.nodes[f]['feed']])
  # print('Bot' if G.nodes[agent]['bot'] else 'Human', 'posted', meme, 'to', G.in_degree(agent), 'followers', flush=True)
  # b: debug
  num_human_memes = [
      1
      for i in G.nodes[agent]["feed"]
      for agent in G.nodes
      if G.nodes[agent]["bot"] == False
  ]

  return count, sum(num_human_memes)

# calculate average quality of memes in system
# b: count_bot is not used here 
def measure_average_quality(G, count_bot=False):
  total = 0
  count = 0
  for agent in G.nodes:
    if count_bot == True or G.nodes[agent]['bot'] == False:
      for m in G.nodes[agent]['feed']:
        total += m[0] 
        count += 1
  return total / count


# calculate fraction of low-quality memes in system
#
def measure_average_zero_fraction(G):
  count = 0
  zeros = 0 
  for agent in G.nodes:
    if G.nodes[agent]['bot'] == False:
      for m in G.nodes[agent]['feed']:
        count += 1
        if m[0] == 0: 
          zeros += 1 
  return zeros / count


# new network from old but replace feed with average quality
# (used for Gephi viz)
#
def add_avq_to_net(G):
  newG = G.copy()
  for agent in newG.nodes:
    if len(newG.nodes[agent]['feed']) < 1:
      print('Bot' if newG.nodes[agent]['bot'] else 'Human', 'has empty feed')
    newG.nodes[agent]['feed'] = float(statistics.mean([m[0] for m in G.nodes[agent]['feed']]))
  return newG


# main simulation 
# steady state is determined by small relative change in average quality
# returns average quality at steady state 
# default epsilon=0.001 is threshold used to check for steady-state convergence
# default theta=1 is the flooding factor for bots
#
@profile
def simulation(preferential_targeting_flag, 
               return_net=False,
               count_forgotten=False,
               track_meme=False,
               network=None, 
               verbose=False,
               epsilon=0.001,
               mu=0.5,
               phi=1,
               gamma=0.1,
               alpha=15,
               theta=1):
  
  if network is None:
    network = init_net(preferential_targeting_flag, gamma=gamma)
  n_agents = nx.number_of_nodes(network)

  # prepare for bookkeeping by resetting counters in case of notebook execution
  track_memes.popularity = {}
  track_memes.bad_popularity = {}
  get_meme.id = 0

  # main loop
  total_memes = 0  # b: count memes
  hum_memes = 0  # b:debug
  old_quality = 1
  quality_diff = 1
  time_steps = 0

  # b: debug
  print('Nodes: %s - Edges: %s' %(network.number_of_nodes(), network.number_of_edges()))
  in_deg = [
      deg for node, deg in network.in_degree(network.nodes())
  ]  # number of followers
  print("Avg in deg", round(sum(in_deg) / len(in_deg), 2))

  while quality_diff > epsilon: 
    if verbose:
      # print('time_steps = {}, q = {}, diff = {}'.format(time_steps, old_quality, quality_diff), flush=True) 
      print(
                "time_steps = {}, q = {}, diff = {}, unique/human memes = {}/{}, all memes ={}".format(
                    time_steps,
                    old_quality,
                    quality_diff,
                    model.get_meme.id,
                    hum_memes,
                    total_memes,
                ),
                flush=True,
            )
    time_steps += 1
    for _ in range(n_agents):
      num_memes, hum_memes = simulation_step(network,
                      count_forgotten_memes=count_forgotten,
                      track_meme=track_meme,
                      mu=mu, phi=phi, alpha=alpha, theta=theta) 
      #debug:
      total_memes += num_memes
    # use exponential moving average for convergence
    new_quality = 0.8 * old_quality + 0.2 * measure_average_quality(network)
    quality_diff = abs(new_quality - old_quality) / old_quality if old_quality > 0 else 0
    old_quality = new_quality

  # remove live memes from popularity data, so track extinct memes only
  if track_meme:
    live_memes = set()
    for agent in network.nodes:
      live_memes.update(set(network.nodes[agent]['feed']))
    for meme in live_memes:
      track_memes.popularity.pop(meme, None)

  if return_net:
    return (new_quality, network)
  else:
    return new_quality


# relationship between indegree (#followers) and low-quality in humans
#
def quality_vs_degree(G):
  avg_quality = {}
  n_zeros = {}
  for agent in G.nodes:
    if G.nodes[agent]['bot'] == False:
      count = 0
      total = 0
      zeros = 0
      for m in G.nodes[agent]['feed']:
        count += 1
        total += m[0]
        if m[0] == 0:
          zeros += 1
      k = G.in_degree(agent)
      if count > 0:
        if k not in avg_quality:
          avg_quality[k] = []
          n_zeros[k] = []
        avg_quality[k].append(total/count)
        n_zeros[k].append(zeros)
  for k in avg_quality:
    avg_quality[k] = statistics.mean(avg_quality[k])
  for k in n_zeros:
    n_zeros[k] = statistics.mean(n_zeros[k])
  return(avg_quality, n_zeros)


# count number of humans who follow at least one bot
#
def bot_followers(G):
  n = 0
  for agent in G.nodes:
    if G.nodes[agent]['bot'] == False:
      for friend in G.successors(agent):
        if G.nodes[friend]['bot']:
          n += 1
          break
  return n


# similar to main simulation but run for fixed time 
# and return avg quality over time
#
def simulation_timeline(preferential_targeting_flag, max_time_steps=10, gamma=0.1):
  quality_timeline = []
  for time_steps in range(max_time_steps):
     quality_timeline.append([])
  for _ in range(n_runs):
    network = init_net(preferential_targeting_flag, gamma=gamma)
    n_agents = nx.number_of_nodes(network)
    for time_steps in range(max_time_steps):
      for _ in range(n_agents):
        simulation_step(network, count_forgotten_memes=False)
      quality = measure_average_quality(network)
      quality_timeline[time_steps].append(quality)
  for time_steps in range(max_time_steps):
    quality_timeline[time_steps] = statistics.mean(quality_timeline[time_steps])
  return quality_timeline 


# CALCULATE beta AND gamma 
# returns (n_bots, n_humans, beta, gamma)
#
def calculate_beta_gamma(RT):
    n_bots = 0
    for n in RT.nodes:
        if RT.nodes[n]['bot']:
            n_bots += 1
    n_humans = RT.number_of_nodes() - n_bots
    sum_of_of_gammas = 0
    for n in RT.nodes:
        if not RT.nodes[n]['bot']:
            bot_friends = 0
            for friend in RT.successors(n):
                if RT.nodes[friend]['bot']:
                    bot_friends += 1
            sum_of_of_gammas += bot_friends / n_bots    
    return(n_bots, n_humans, n_bots / n_humans, sum_of_of_gammas / n_humans)

