# from InfoSystem import InfoSystem
from ig_InfoSys import InfoSystem
from profileit import profile
import graphutils
import ig_utils
from utils import *
import igraph
import networkx as nx 
from pathlib import Path
import pickle as pkl 


ABS_PATH = "/N/u/baotruon/Carbonate/marketplace/igraphvsnx"
# ABS_PATH = ''
DATA_PATH = os.path.join(ABS_PATH, "data")
# TODO: save network as .gml.gz, keep only friend relationships

@profile
def bao_simulation(mode='igraph'):
    path = DATA_PATH

    follower_path = os.path.join(path, "follower_network.gml")
    infosys_path = os.path.join(path, mode, "network.gml")
    
    net_specs = {
        "targeting_criterion": "hubs",
        "human_network": follower_path,
        "track_meme": True,
        "n_humans": 1000,
        "beta": 0.01,
        "gamma": 0.001,
        "verbose": True,
    }

    infosys_specs = {
        "preferential_targeting": None,
        "verbose": True,
        "mu": 0.5,
        "phi": 1,
        "alpha": 15,
    }

    if make_sure_file_exists(infosys_path) is False:
        if mode=='igraph':
            G = ig_utils.init_net(**net_specs)
            if make_sure_dir_exists(path, mode):
                G.write_gml(infosys_path)
        else:
            G = graphutils.init_net(**net_specs)
            # nx.write_edgelist(G, "follower_net.edgelist.gz")
            if make_sure_dir_exists(path, mode):
                nx.write_gml(G, infosys_path)

    print("Create InfoSystem instance..")
    follower_sys = InfoSystem(os.path.join(path,mode, "network.gml"), mode=mode, **infosys_specs)
    print("Start simulation (mode: %s).." %mode)
    all_feeds, meme_popularity, avg_quality = follower_sys.simulation()
    print("average quality for follower network:", avg_quality)
    
    final_allmemes = os.path.join(path, mode, "meme.pkl")
    pkl.dump(all_feeds, open(final_allmemes, 'wb'))

    final_meme_popularity = os.path.join(path, mode, "meme_popularity.pkl")
    pkl.dump(meme_popularity, open(final_meme_popularity, 'wb'))

if __name__ == "__main__":
    bao_simulation(mode='igraph')
    # bao_simulation(mode='nx')

