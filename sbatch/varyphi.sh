#!/bin/bash
#####  Constructed by HPC everywhere #####
#SBATCH --mail-user=baotruon@iu.edu
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=15
#SBATCH --time=3-23:59:00
#SBATCH --mail-type=FAIL,BEGIN,END
#SBATCH --job-name=varyphi

######  Module commands #####
source /N/u/baotruon/Carbonate/miniconda3/etc/profile.d/conda.sh
conda activate graph


######  Job commands go below this line #####
cd /N/u/baotruon/Carbonate/marketplace
echo '###### vary phi gamma ######'
snakemake --nolock --snakefile workflow/rules/vary_phigamma.smk --cores 15