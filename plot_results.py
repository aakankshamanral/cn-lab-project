
import os
import pandas as pd
import matplotlib.pyplot as plt

os.makedirs("results/graphs", exist_ok=True)
df = pd.read_csv("results/qos_results.csv")

metrics = [
    ("tcp_throughput_mbps", "TCP Throughput (Mbps)"),
    ("udp_throughput_mbps", "UDP Throughput (Mbps)"),
    ("udp_jitter_ms", "UDP Jitter (ms)"),
    ("udp_packet_loss_percent", "UDP Packet Loss (%)"),
    ("udp_latency_ms", "UDP Latency (ms)"),
]

for column, title in metrics:
    ax = df.plot(
        x="scenario", y=column, kind="bar",
        legend=False, rot=0
    )
    ax.set_title(title)
    ax.set_ylabel(title)
    plt.tight_layout()
    filename = column + ".png"
    plt.savefig("results/graphs/" + filename, dpi=200)
    plt.close()

print("Graphs saved in results/graphs/")
