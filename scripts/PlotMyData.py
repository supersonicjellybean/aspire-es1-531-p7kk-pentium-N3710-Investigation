import os
import pandas as pd
import matplotlib.pyplot as plt

print('Ensure csv file and this program are in the same directory before running')
whatsthename = input('Enter CSV name (do not include .csv): ').strip()
file_path = whatsthename + '.csv'

cols = ['timestamp', 'cpu0', 'cpu1', 'cpu2', 'cpu3']

try:
    df = pd.read_csv(file_path, header=None, names=cols)
except FileNotFoundError:
    print(f"Error: Could not find '{file_path}'. Did you add .csv to the end? Recheck the filename and make sure that this program and your dataset are in the same directory.")
    exit()
except Exception as e:
    print(f"An unexpected error occurred while reading the file: {e}")
    exit()

sample_nums = df.index

fig, axes = plt.subplots(4, 1, figsize=(10, 5.625), sharex=True, sharey=True)

colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
for i in range(4):
    axes[i].scatter(sample_nums, df[f'cpu{i}'] / 1000, color=colors[i], s=2, alpha=0.4)
    axes[i].set_ylabel(f'CPU {i}\n(MHz)', fontsize=9)
    axes[i].grid(True, linestyle=':', alpha=0.6)

axes[0].set_title(f'CPU Frequency per Core ({whatsthename})', fontsize=12)
axes[3].set_xlabel('Sample Number', fontsize=10)

plt.tight_layout()
os.makedirs('plots', exist_ok=True)
plt.savefig(f'plots/{whatsthename}_scatter_900DPI.png', dpi=900)
plt.savefig(f'plots/{whatsthename}_scatter_Vector.svg', format='svg')
plt.show()