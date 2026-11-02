
import os
import csv
import random
import statistics
import matplotlib.pyplot as plt

# QOS PROJECT: TWO-SUBNET NETWORK SIMULATION

OUTPUT_DIR = "results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SIM_TIME = 20.0
LINK_MBPS = 5.0
PACKET_BYTES = 1000
BUFFER_LIMIT = 100
PROPAGATION_MS = 10.0
SEED = 42

# Logical topology matching Packet Tracer
DEVICES = {
    "PC0": "192.168.1.2",
    "PC1": "192.168.1.3",
    "Server0": "192.168.1.10",
    "Router0_left": "192.168.1.1",
    "Router0_right": "192.168.2.1",
    "PC2": "192.168.2.2",
    "PC3": "192.168.2.3",
    "Server1": "192.168.2.10",
}

print("NETWORK TOPOLOGY")
print("PC0, PC1, Server0 -> Switch0 -> Router0")
print("Router0 -> Switch1 -> PC2, PC3, Server1")
print("Left LAN: 192.168.1.0/24")
print("Right LAN: 192.168.2.0/24")
print("Router bottleneck:", LINK_MBPS, "Mbps")


def generate_traffic(seed):
    """Generate repeatable UDP and TCP packet arrivals."""
    rng = random.Random(seed)
    packets = []

    # Offered traffic exceeds link capacity: 3 + 4 > 5 Mbps.
    rates = {"UDP": 3.0, "TCP": 4.0}

    for flow, rate_mbps in rates.items():
        packets_per_second = (
            rate_mbps * 1_000_000 / (PACKET_BYTES * 8)
        )
        arrival = 0.0

        while True:
            arrival += rng.expovariate(packets_per_second)
            if arrival >= SIM_TIME:
                break

            packets.append({
                "arrival": arrival,
                "flow": flow,
                "size": PACKET_BYTES,
            })

    packets.sort(key=lambda p: p["arrival"])
    return packets


def simulate(qos_enabled, seed=SEED):
    packets = generate_traffic(seed)

    # Queue and metrics
    queue = []
    next_packet = 0
    current_time = 0.0
    busy_until = 0.0

    sent = {"UDP": 0, "TCP": 0}
    delivered = {"UDP": 0, "TCP": 0}
    dropped = {"UDP": 0, "TCP": 0}
    udp_delays = []

    service_time = PACKET_BYTES * 8 / (
        LINK_MBPS * 1_000_000
    )

    def serve_one(now):
        """Serve one packet; UDP has priority when QoS is enabled."""
        nonlocal busy_until

        if not queue:
            return

        if qos_enabled:
            # Strict priority: UDP before TCP.
            udp_indices = [
                i for i, p in enumerate(queue)
                if p["flow"] == "UDP"
            ]
            index = udp_indices[0] if udp_indices else 0
        else:
            # FIFO: earliest-arriving packet first.
            index = 0

        packet = queue.pop(index)
        finish = now + service_time
        busy_until = finish

        if finish <= SIM_TIME:
            flow = packet["flow"]
            delivered[flow] += 1

            if flow == "UDP":
                delay_ms = (
                    (finish - packet["arrival"]) * 1000
                    + PROPAGATION_MS
                )
                udp_delays.append(delay_ms)

    while next_packet < len(packets) or queue:
        # If idle, start serving queued traffic.
        if not queue and next_packet < len(packets):
            current_time = max(
                current_time, packets[next_packet]["arrival"]
            )

        # Process all arrivals up to current time.
        while (
            next_packet < len(packets)
            and packets[next_packet]["arrival"] <= current_time
        ):
            packet = packets[next_packet]
            next_packet += 1
            flow = packet["flow"]
            sent[flow] += 1

            if len(queue) >= BUFFER_LIMIT:
                dropped[flow] += 1
            else:
                queue.append(packet)

        # If the link is free, serve a packet.
        if current_time >= busy_until:
            if queue:
                serve_one(current_time)
            elif next_packet < len(packets):
                current_time = packets[next_packet]["arrival"]
                continue
            else:
                break

        # Advance to the next arrival or service completion.
        next_arrival = (
            packets[next_packet]["arrival"]
            if next_packet < len(packets)
            else float("inf")
        )

        if busy_until <= next_arrival:
            current_time = busy_until
        else:
            current_time = next_arrival

        # Account for arrivals that occurred while serving.
        # The next loop processes them at their arrival time.

    def throughput(flow):
        return (
            delivered[flow] * PACKET_BYTES * 8
            / SIM_TIME / 1_000_000
        )

    jitter = (
        statistics.mean(
            abs(b - a)
            for a, b in zip(udp_delays, udp_delays[1:])
        )
        if len(udp_delays) > 1 else 0.0
    )

    return {
        "scenario": "QoS Enabled" if qos_enabled else "Baseline",
        "topology": "6 end devices, 2 switches, 1 router",
        "left_subnet": "192.168.1.0/24",
        "right_subnet": "192.168.2.0/24",
        "router_link_mbps": LINK_MBPS,
        "tcp_offered_mbps": 4.0,
        "udp_offered_mbps": 3.0,
        "tcp_throughput_mbps": round(throughput("TCP"), 3),
        "udp_throughput_mbps": round(throughput("UDP"), 3),
        "udp_latency_ms": round(
            statistics.mean(udp_delays) if udp_delays else 0, 3
        ),
        "udp_jitter_ms": round(jitter, 3),
        "udp_packet_loss_percent": round(
            100 * dropped["UDP"] / max(sent["UDP"], 1), 3
        ),
        "tcp_packets_sent": sent["TCP"],
        "tcp_packets_delivered": delivered["TCP"],
        "udp_packets_sent": sent["UDP"],
        "udp_packets_delivered": delivered["UDP"],
        "udp_packets_dropped": dropped["UDP"],
    }


def make_graphs(results):
    labels = [r["scenario"] for r in results]

    metrics = [
        ("tcp_throughput_mbps", "TCP Throughput (Mbps)",
         "tcp_throughput.png"),
        ("udp_throughput_mbps", "UDP Throughput (Mbps)",
         "udp_throughput.png"),
        ("udp_latency_ms", "UDP Latency (ms)",
         "udp_latency.png"),
        ("udp_jitter_ms", "UDP Jitter (ms)",
         "udp_jitter.png"),
        ("udp_packet_loss_percent", "UDP Packet Loss (%)",
         "udp_packet_loss.png"),
    ]

    graph_dir = os.path.join(OUTPUT_DIR, "graphs")
    os.makedirs(graph_dir, exist_ok=True)

    for column, title, filename in metrics:
        values = [r[column] for r in results]

        plt.figure(figsize=(7, 4))
        plt.bar(labels, values)
        plt.title(title)
        plt.ylabel(title)
        plt.tight_layout()
        plt.savefig(
            os.path.join(graph_dir, filename),
            dpi=200
        )
        plt.close()

    print("Graphs saved in:", graph_dir)


def main():
    print("\nRunning baseline...")
    baseline = simulate(False)

    print("Running QoS-enabled scenario...")
    qos = simulate(True)

    results = [baseline, qos]

    csv_path = os.path.join(
        OUTPUT_DIR, "qos_comparison.csv"
    )

    with open(csv_path, "w", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=results[0].keys()
        )
        writer.writeheader()
        writer.writerows(results)

    print("\nRESULTS COMPARISON")
    print("-" * 65)

    columns = [
        "tcp_throughput_mbps",
        "udp_throughput_mbps",
        "udp_latency_ms",
        "udp_jitter_ms",
        "udp_packet_loss_percent",
    ]

    print(f"{'Metric':32} {'Baseline':>12} {'QoS':>12}")
    for column in columns:
        print(
            f"{column:32} "
            f"{baseline[column]:>12} "
            f"{qos[column]:>12}"
        )

    print("\nCSV saved in:", csv_path)
    make_graphs(results)

    print(
        "\nIMPORTANT: These are simulated results, "
        "not measurements from a live network."
    )


if __name__ == "__main__":
    main()
