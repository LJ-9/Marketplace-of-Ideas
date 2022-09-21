#!/bin/bash
#####  Constructed by HPC everywhere #####
#SBATCH --mail-user=baotruon@iu.edu
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=23
#SBATCH --time=3-23:59:00
#SBATCH --mail-type=FAIL,BEGIN,END
#SBATCH --job-name=strategy_beta

######  Module commands #####
source /N/u/baotruon/Carbonate/miniconda3/etc/profile.d/conda.sh
conda activate graph


######  Job commands go below this line #####
cd /N/u/baotruon/Carbonate/marketplace
echo '###### compare strategies vary beta ######'
snakemake --nolock --snakefile workflow/final_rules/strategies_beta.smk --cores 23