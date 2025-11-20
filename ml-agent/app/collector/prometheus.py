"""
This is my colleague script. Currently unused by us, good for reference.
"""
import logging
import math
import random
import time
import requests
from kubernetes import client, config
import time
from datetime import datetime, timezone
import sys

# port-forward in k8s cluster
PROMETHEUS_URL = 'http://10.244.205.246:9090'

ARIMA_ENERGY = "forecast-arima-energy"
ARIMA_THROUGHPUT = "forecast-arima-throughput"
ARIMA_LATENCY = "forecast-arima-latency"


HOSTNAME_LIST=[
                'cloudskin-k8s-edge-worker-1.novalocal',
                'cloudskin-k8s-control-plane-0.novalocal',
                'cloudskin-k8s-edge-worker-0.novalocal',
                'cloudskin-k8s-edge-worker-2.novalocal'
              ]
NUM_HOSTS=4

#max
MAX_QOS=200 # system max
MAX_ENERGY=18000 # system max
MAX_POWER=300
MAX_LATENCY=2000 # system max
MAX_CPU_COUNT=12000
MAX_USERS = 70

DEFAULT_CLUSTER_TYPES = [{"type": "node58", "cpu": 4.0, "mem": 8.0, "max_power_w": 69.7, "idle_power_w": 36.6 , "latency": 5}, #edge1
                         #{"type": "node127", "cpu": 12.0, "mem": 48.0, "max_power_w": 293.0, "idle_power_w": 124.0, "latency": 291.36}, #cloud
                         {"type": "node313", "cpu": 12.0, "mem": 48.0, "max_power_w": 280.0, "idle_power_w": 162.0, "latency": 30.9}, #cloud
                         {"type": "node169", "cpu": 4.0, "mem": 8.0, "max_power_w": 58.5, "idle_power_w": 19.0, "latency": 14}, #edge0
                        #  {"type": "node169", "cpu": 4.0, "mem": 8.0, "max_power_w": 58.5, "idle_power_w": 19.0, "latency": 73.74}, #edge0
                        #  {"type": "node302", "cpu": 4.0, "mem": 8.0, "max_power_w": 72.5, "idle_power_w": 14.1, "latency": 14}, #edge0
                         {"type": "node280", "cpu": 4.0, "mem": 8.0, "max_power_w": 102.0, "idle_power_w": 21.4, "latency": 3}] #edge2


def get_torchserve_deployment(k8s):
    deployment_list = [
        DeploymentStatus(k8s, "torchserve", "torchservetest", "torchserve",
                         300.0)
    ]
    return deployment_list

def get_host_num_from_host_name(host_name):
    if host_name is None:
        logging.error("get_host_num_from_host_name hostname none error")
        return None
    try:
        return HOSTNAME_LIST.index(host_name)
    except ValueError:
        logging.error("get_host_num_from_host_name hostname index error {}".format(host_name))
        return None 

def get_host_name_from_host_num(host_num):
    if host_num is None:
        logging.error("get_host_name_from_host_num hostnum none error")
        return None
    try:
        return HOSTNAME_LIST[host_num]
    except ValueError:
        logging.error("get_host_name_from_host_num hostnum index error {}".format(host_num))
        return None


class DeploymentStatus:  # Deployment Status (Workload)
    def __init__(self, k8s, name, namespace, container_name, latency_threshold):
        #TODO: later add more, this matters for multiple containers cpu_request, mem_request
        
        # K8s enabled
        self.k8s = k8s
        # csv file?
        # self.csv = self.namespace + '_' + self.name + '.csv'
        
        #app name/deployment name
        self.name = name
        # namespace
        self.namespace = namespace
        # containername
        self.container_name = container_name

        #app not change (constraints)
        self.sla = latency_threshold
        # self.cpu_request = cpu_request
        # self.mem_request = mem_request        

        #node change
        self.current_host = ""
        self.node_cpu_count = []
        self.node_energy = []
        self.node_power = []

        # app change
        self.current_pod = ""
        self.cpu_count = 0
        self.energy = 0
        self.power = 0 
        self.latency = 0
        self.throughput = 0
        self.users = 0
        
        # Forecast
        self.energy_forecast = 0
        self.throughput_forecast = 0
        self.latency_forecast = 0

        # other metrics: time between API calls if failure happens
        self.sleep = 1

        if self.k8s:  # Real env: consider a k8s cluster
            logging.info("[Deployment] Consider a real k8s cluster ... ")
            # out of cluster!
            # self.config.load_kube_config()

            # In cluster config!
            self.config = config.load_incluster_config()

            # Create a ApiClient with our config
            self.client = client.ApiClient(self.config)
            # v1 api
            self.v1 = client.CoreV1Api(self.client)
            # apps v1 api
            self.apps_v1 = client.AppsV1Api(self.client)
            
            #first update
            self.update_obs_k8s()
        else:
            print("simulation")

    def update_obs_k8s(self):
        while True:
            try:
                # Get list of Pods for the deployment
                pod_list = self.v1.list_namespaced_pod(
                    namespace=self.namespace
                )

                # Find the most recently created Pod
                latest_pod = max(pod_list.items, key=lambda pod: pod.metadata.creation_timestamp, default=None)

                if latest_pod and latest_pod.spec.node_name:
                    logging.info(f"Latest Pod {latest_pod.metadata.name} is running on node: {latest_pod.spec.node_name}")
                    self.current_host = get_host_num_from_host_name(latest_pod.spec.node_name)
                    self.current_pod = latest_pod.metadata.name
                    break
                else:
                    logging.warning("No running pod found to retrieve nodeName.")
            except Exception as e:
                logging.error(f"Unexpected error occurred: {type(e).__name__}: {e}")
                time.sleep(2)

            # retries += 1
            # if retries >= max_retries:
            #     logging.error("ERROR: Max retries reached. Hostname not found.")
            #     break  # Exit after max retries

        # Update Forecast
        # self.energy_forecast = convert_to_milli_cpu(self.deployment_object.metadata.annotations[ARIMA_ENERGY])
        # self.throughput_forecast = convert_to_milli_cpu(self.deployment_object.metadata.annotations[ARIMA_THROUGHPUT])
        # self.latency_forecast = convert_to_mega_memory(self.deployment_object.metadata.annotations[ARIMA_LATENCY])
        # logging.info("[Deployment] Torchserve forecast - energy: {} - throughput: {} - latency: {} |".format(self.energy_forecast, self.throughput_forecast, self.latency_forecast))

        while True:
            # Update obs
            # query_node_cpu_count = 'kepler:cpu_rate:1m:by_node{instance=''"' + get_host_name_from_host_num(self.current_host) + '"}'
            # query_node_power = 'kepler:node_platform_watt:1m:by_node{instance=''"' + get_host_name_from_host_num(self.current_host) + '"}'
            # query_node_energy = 'kepler:node_platform_joules:1m:by_node{instance=''"' + get_host_name_from_host_num(self.current_host) + '"}'
            query_node_cpu_count = 'kepler:cpu_rate:1m:by_node'
            query_node_power = 'kepler:node_platform_watt:1m:by_node'
            query_node_energy = 'kepler:node_platform_joules:1m:by_node'

            # -------------- NODE metrics ----------------
            self.node_cpu_count = self.fetch_prom_list(query_node_cpu_count, MAX_CPU_COUNT)
            self.node_power = self.fetch_prom_list(query_node_power, MAX_POWER)
            self.node_energy = self.fetch_prom_list(query_node_energy, MAX_ENERGY)

            # self.node_cpu_count = random.randint(1, MAX_ENERGY)
            # self.node_energy = random.randint(1, MAX_ENERGY)
            # self.node_power = random.randint(1, MAX_ENERGY)

            #--------------user metrics-------------------
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
                net_latency = DEFAULT_CLUSTER_TYPES[self.current_host]["latency"]
                self.latency = self.fetch_prom(query_latency, MAX_LATENCY) + net_latency
                self.throughput = self.fetch_prom(query_throughput, MAX_QOS)

                # self.cpu_count = random.randint(1, MAX_CPU_COUNT)
                # self.energy = random.randint(1, MAX_ENERGY)
                # self.power = random.randint(1, MAX_ENERGY) 
                # self.latency = random.randint(1, MAX_QOS)
                # self.throughput = random.randint(1, MAX_QOS)
                  
            #check spike
            if self.node_power[self.current_host] >= self.power:
                break
            else:
                logging.info("node {} power{} <app power {} retry".format(self.current_host, self.node_power, self.power))
            return

 
    def migrate_application(self, host_num):
        if host_num < NUM_HOSTS:
            if self.k8s:
                logging.info("migrate {} to {}".format(self.current_host, host_num))
                host_name = get_host_name_from_host_num(host_num)
                if host_name is not None:
                    return self.patch_deployment(host_name)
            # else:
            #     #simulation
            #     self.current_host = host_num
            #     return True
        else:
            logging.error("host not known")

    def patch_deployment(self, host_name):
        # Prepare the patch, which sets the nodeSelector
        patch_body = {
            "spec": {
                "template": {
                    "spec": {
                        "nodeSelector": {"kubernetes.io/hostname":host_name}
                    }
                }
            }
        }

        # print(f"agent is patch deployment to node - {patch_body}")
        
        try:
            self.apps_v1.patch_namespaced_deployment(
                name=self.name,
                namespace=self.namespace,
                body=patch_body
            )
            logging.info("update_deployment_with_patch succeeded")
            return True
        except client.api_client.rest.ApiException as e:
            logging.error(f"update_deployment_with_patch failed: {e}")
            print("Retrying in {}s...".format(self.sleep))
            time.sleep(self.sleep)
            return self.patch_deployment(host_name)
        

    # def print_deployment(self):
    #     logging.info("[Deployment] Name: " + str(self.name))
    #     logging.info("[Deployment] Namespace: " + str(self.namespace))
    #     logging.info("[Deployment] Pod Names: " + str(self.name))
    #     # logging.info("[Deployment] CPU Usage (in m): " + str(self.cpu_usage))
    #     # logging.info("[Deployment] MEM Usage (in Mi): " + str(self.mem_usage))
    #     logging.info("[Deployment] Energy (in J): " + str(self.energy))
    #     logging.info("[Deployment] Throughput (in qps): " + str(self.throughput))
    #     logging.info("[Deployment] Latency (in ms): " + str(self.latency))

    def fetch_prom(self, query, max, retry_count = 0, error_count = 0):
        max_retries = 120

        if retry_count >= max_retries:
            logging.info("max retries reached. stopping ...")
            sys.exit("Stopping agent due to repeated failures.") 

        try:
            response = requests.get(PROMETHEUS_URL + '/api/v1/query',
                                    params={'query': query})

        except requests.exceptions.RequestException as e:
            print("ERROR {}...  Retrying get metric in {}...".format(e, self.sleep))
            time.sleep(self.sleep)
            return self.fetch_prom(query, max, retry_count + 1, error_count)

        if response.json()['status'] != "success":
            print("Error processing the request: " + response.json()['status'])
            print("The Error is: " + response.json()['error'])
            print("Retrying in {}s...".format(self.sleep))
            time.sleep(self.sleep)
            return self.fetch_prom(query, max, retry_count + 1, error_count)

        result = response.json()['data']['result']
        if result:
            value_str = result[0]["value"][1]
            try:
                value = float(value_str)
                if math.isnan(value) or value == 0.0 or math.isinf(value):
                    raise ValueError("Invalid value (NaN or 0)")
                if value > float(max):
                    logging.info("Invalid value {} > {}".format(value, max))
                    time.sleep(self.sleep)
                    self.fetch_prom(query, max, retry_count + 1, error_count) 
                return value
            except ValueError:
                logging.info("Retrying in {}s... metric result is invalid or zero: {}.".format(self.sleep, result))
                if error_count >= 3:
                    logging.info("3 invalid number reached. restarting kepler...")
                    self.restart_kepler_daemonset()
                    time.sleep(60)
                    retry_count = 0
                    error_count = 0
                time.sleep(self.sleep)
                return self.fetch_prom(query, max, retry_count + 1, error_count + 1)
        else:
            print("Retrying {} {} time get metric in {}s...".format(retry_count, query, self.sleep))
            time.sleep(self.sleep)
            return self.fetch_prom(query, max, retry_count + 1, error_count)
        # if result and result[0]["value"][1] not in [None, "NaN"]:
        #     return float(result[0]["value"][1])
        # else:
        #     print("Retrying in {}s..result is none {}.".format(self.sleep,result))
        #     time.sleep(self.sleep)
        #     return self.fetch_prom(query) 

    def fetch_prom_list(self, query, max, retry_count = 0, error_count = 0):
        max_retries = 120

        if retry_count >= max_retries:
            logging.info("max retries reached. stopping ...")
            sys.exit("Stopping agent due to repeated failures.") 

        try:
            response = requests.get(PROMETHEUS_URL + '/api/v1/query',
                                    params={'query': query})

        except requests.exceptions.RequestException as e:
            print("ERROE {}...  Retrying get list in {}...".format(e, self.sleep))
            time.sleep(self.sleep)
            return self.fetch_prom_list(query, max, retry_count + 1, error_count)

        if response.json()['status'] != "success":
            print("Error processing the request: " + response.json()['status'])
            print("The Error is: " + response.json()['error'])
            print("Retrying get list in {}s...".format(self.sleep))
            time.sleep(self.sleep)
            return self.fetch_prom_list(query, max, retry_count + 1, error_count)

        result = response.json()['data']['result']
        # print(result)
        if result:
            # filtered_values_ordered = [
            #     entry['value'][1] for hostname in HOSTNAME_LIST
            #     for entry in result if entry['metric']['instance'] == hostname
            # ]
            # return filtered_values_ordered
            filtered_values_ordered = []
            for hostname in HOSTNAME_LIST:
                for entry in result:
                    if entry['metric']['instance'] == hostname:
                        value_str = entry['value'][1]
                        try:
                            value = float(value_str)
                            if math.isnan(value) or value == 0.0:
                                raise ValueError("Invalid value (NaN or 0)")
                            if value > float(max):
                                logging.info("Invalid value {} > {}".format(value, max))
                                time.sleep(self.sleep)
                                self.fetch_prom_list(query, max, retry_count + 1, error_count)
                            filtered_values_ordered.append(value)
                        except ValueError:
                            logging.info("Retry {} times, in {}s... Invalid get list value {}.".format(retry_count + 1, self.sleep, filtered_values_ordered))
                            if error_count >= 3:
                                logging.info("3 invalid number reached. restarting kepler...")
                                self.restart_kepler_daemonset()
                                time.sleep(60)
                                retry_count = 0
                                error_count = 0
                            time.sleep(self.sleep)
                            return self.fetch_prom_list(query, max, retry_count + 1, error_count + 1)
            return filtered_values_ordered
        else:
            print("Retrying get list in {}s...".format(self.sleep))
            time.sleep(self.sleep)
            return self.fetch_prom_list(query, max, retry_count + 1, error_count)

    def restart_kepler_daemonset(self):
        try:
            config.load_incluster_config()
            apps_v1 = client.AppsV1Api()
            body = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": datetime.now(timezone.utc).isoformat()
                            }
                        }
                    }
                }
            }
            apps_v1.patch_namespaced_daemon_set(
                    name="kepler-exporter",
                    namespace="kepler",
                    body=body
            )
            logging.info("[Kepler Restart] Successfully triggered DaemonSet restart")
        except Exception as e:
            logging.error(f"[Kepler Restart] Failed to restart Kepler DaemonSet: {e}")
            print("Retrying in {}s...".format(self.sleep))
            time.sleep(self.sleep)
            return self.restart_kepler_daemonset()[rocky@cloudskin-k8s-control-plane-0 envs]$ 

