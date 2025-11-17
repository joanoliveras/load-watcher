"""
Prometheus collector for collect-forecast-export.
To be defined all the queries and exact metrics to collect.
"""
while True:
            query_node_cpu_count = 'kepler:cpu_rate:1m:by_node'
            query_node_power = 'kepler:node_platform_watt:1m:by_node'
            query_node_energy = 'kepler:node_platform_joules:1m:by_node'
            # -------------- NODE metrics ----------------
            self.node_cpu_count = self.fetch_prom_list(query_node_cpu_count, MAX_CPU_COUNT)
            self.node_power = self.fetch_prom_list(query_node_power, MAX_POWER)
            self.node_energy = self.fetch_prom_list(query_node_energy, MAX_ENERGY)
            # --------------user metrics-------------------
            query_users = 'locust_current_users'
            self.users = self.fetch_prom(query_users, MAX_USERS)
            if self.name == 'torchserve':
                # logging.info("torchserve_app metrics")
                query_cpu_count = 'kepler:container_torchserve_cpu_rate:1m{pod_name=''"' + self.current_pod + '"}'
                query_energy = 'kepler:container_torchserve_joules:1m{pod_name=''"' + self.current_pod + '"}'
                query_power = 'kepler:container_torchserve_watt:1m{pod_name=''"' + self.current_pod + '"}'
                query_latency = 'ts:latency:1m:ms{pod=''"' + self.current_pod + '"}'
                query_throughput = 'ts:throughput:1m:rps{pod=''"' + self.current_pod + '"}'
                self.cpu_count = self.fetch_prom(query_cpu_count, MAX_CPU_COUNT)
                self.energy = self.fetch_prom(query_energy, MAX_ENERGY)
                self.power = self.fetch_prom(query_power, MAX_POWER)
                self.latency = self.fetch_prom(query_latency, MAX_LATENCY)
                self.throughput = self.fetch_prom(query_throughput, MAX_QOS)
