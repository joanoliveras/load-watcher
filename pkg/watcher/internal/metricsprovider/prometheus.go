/*
Copyright 2020

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

package metricsprovider

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"io/ioutil"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"k8s.io/client-go/transport"

	"github.com/paypal/load-watcher/pkg/watcher"
	"github.com/prometheus/client_golang/api"
	v1 "github.com/prometheus/client_golang/api/prometheus/v1"
	"github.com/prometheus/common/config"
	"github.com/prometheus/common/model"
	log "github.com/sirupsen/logrus"

	_ "k8s.io/client-go/plugin/pkg/client/auth/oidc"
)

const (
	EnableOpenShiftAuth          = "ENABLE_OPENSHIFT_AUTH"
	K8sPodCAFilePath             = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
	DefaultPromAddress           = "http://prometheus-k8s:9090"
	promStd                      = "stddev_over_time"
	promAvg                      = "avg_over_time"
	promLatest                   = "latest"
	// Pseudo metric names for latest-mode helpers
	promKeplerHostPlatformJoulesIncr1m = "kepler_node_platform_joules_total__increase1m"
	promContainerCpuRate1m             = "container_cpu_usage_seconds_total__rate1m"
	promKeplerContainerJoulesRate1m    = "kepler_container_joules_total__rate1m"
	promKeplerContainerJoulesIncr1m    = "kepler_container_joules_total__increase1m"
	// Recording rule names (optional; used when WATCH_RECORDING_RULES=true)
	ruleNodeCpuByNode       = "kepler:cpu_rate:1m:by_node"
	ruleNodePowerByNode     = "kepler:node_platform_watt:1m:by_node"
	ruleNodeEnergyByNode    = "kepler:node_platform_joules:1m:by_node"
	ruleAppCpuTorchServe    = "kepler:container_torchserve_cpu_rate:1m"
	ruleAppPowerTorchServe  = "kepler:container_torchserve_watt:1m"
	ruleAppEnergyTorchServe = "kepler:container_torchserve_joules:1m"
	ruleTsLatencyMs         = "ts:latency:1m:ms"
	ruleTsThroughputRps     = "ts:throughput:1m:rps"
	promCpuMetric                = "instance:node_cpu:ratio"
	promMemMetric                = "instance:node_memory_utilisation:ratio"
	promTransBandMetric          = "instance:node_network_transmit_bytes:rate:sum"
	promTransBandDropMetric      = "instance:node_network_transmit_drop_excluding_lo:rate5m"
	promRecBandMetric            = "instance:node_network_receive_bytes:rate:sum"
	promRecBandDropMetric        = "instance:node_network_receive_drop_excluding_lo:rate5m"
	promDiskIOMetric             = "instance_device:node_disk_io_time_seconds:rate5m"
	promScaphHostPower           = "scaph_host_power_microwatts"
	promScaphHostJoules          = "scaph_host_energy_microjoules"
	promKeplerHostCoreJoules     = "kepler_node_core_joules_total"
	promKeplerHostUncoreJoules   = "kepler_node_uncore_joules_total"
	promKeplerHostDRAMJoules     = "kepler_node_dram_joules_total"
	promKeplerHostPackageJoules  = "kepler_node_package_joules_total"
	promKeplerHostOtherJoules    = "kepler_node_other_joules_total"
	promKeplerHostGPUJoules      = "kepler_node_gpu_joules_total"
	promKeplerHostPlatformJoules = "kepler_node_platform_joules_total"
	promKeplerHostEnergyStat     = "kepler_node_energy_stat"
	allHosts                     = "all"
	hostMetricKey                = "instance"
)

type promClient struct {
	client     api.Client
	latestMode bool
	watchPod   string
	watchNS    string
	watchPodRx string
	minimal    bool
	useRules   bool
	includeTS  bool
}

func loadCAFile(filepath string) (*x509.CertPool, error) {
	caCert, err := ioutil.ReadFile(filepath)
	if err != nil {
		return nil, err
	}

	caCertPool := x509.NewCertPool()
	if ok := caCertPool.AppendCertsFromPEM(caCert); !ok {
		return nil, fmt.Errorf("failed to append CA certificate to the pool")
	}

	return caCertPool, nil
}

func NewPromClient(opts watcher.MetricsProviderOpts) (watcher.MetricsProviderClient, error) {
	if opts.Name != watcher.PromClientName {
		return nil, fmt.Errorf("metric provider name should be %v, found %v", watcher.PromClientName, opts.Name)
	}

	var client api.Client
	var err error
	var promToken, promAddress = "", DefaultPromAddress
	if opts.AuthToken != "" {
		promToken = opts.AuthToken
	}
	if opts.Address != "" {
		promAddress = opts.Address
	}
	// Detect "latest" mode via env
	var latestMode bool
	if mode, ok := os.LookupEnv(watcher.WatchModeEnvKey); ok && strings.ToLower(mode) == "latest" {
		latestMode = true
	}
	watchPod, _ := os.LookupEnv("WATCH_POD")
	watchNS, _ := os.LookupEnv("WATCH_NAMESPACE")
	watchPodRx, _ := os.LookupEnv("WATCH_POD_REGEX")
	var minimal bool
	if m, ok := os.LookupEnv("WATCH_MINIMAL"); ok && strings.ToLower(m) == "true" {
		minimal = true
	}
	var useRules bool
	if u, ok := os.LookupEnv("WATCH_RECORDING_RULES"); ok && strings.ToLower(u) == "true" {
		useRules = true
	}
	var includeTS bool
	if t, ok := os.LookupEnv("WATCH_INCLUDE_TS"); ok && strings.ToLower(t) == "true" {
		includeTS = true
	}

	// Ignore TLS verify errors if InsecureSkipVerify is set
	roundTripper := api.DefaultRoundTripper

	// Check if EnableOpenShiftAuth is set.
	_, enableOpenShiftAuth := os.LookupEnv(EnableOpenShiftAuth)
	if enableOpenShiftAuth {
		// Retrieve Pod CA cert
		caCertPool, err := loadCAFile(K8sPodCAFilePath)
		if err != nil {
			return nil, fmt.Errorf("Error loading CA file: %v", err)
		}

		// Get Prometheus Host
		u, _ := url.Parse(opts.Address)
		roundTripper = transport.NewBearerAuthRoundTripper(
			opts.AuthToken,
			&http.Transport{
				Proxy: http.ProxyFromEnvironment,
				DialContext: (&net.Dialer{
					Timeout:   30 * time.Second,
					KeepAlive: 30 * time.Second,
				}).DialContext,
				TLSHandshakeTimeout: 10 * time.Second,
				TLSClientConfig: &tls.Config{
					RootCAs:    caCertPool,
					ServerName: u.Host,
				},
			},
		)
	} else if opts.InsecureSkipVerify {
		roundTripper = &http.Transport{
			Proxy: http.ProxyFromEnvironment,
			DialContext: (&net.Dialer{
				Timeout:   30 * time.Second,
				KeepAlive: 30 * time.Second,
			}).DialContext,
			TLSHandshakeTimeout: 10 * time.Second,
			TLSClientConfig:     &tls.Config{InsecureSkipVerify: true},
		}
	}

	if promToken != "" {
		client, err = api.NewClient(api.Config{
			Address:      promAddress,
			RoundTripper: config.NewAuthorizationCredentialsRoundTripper("Bearer", config.NewInlineSecret(opts.AuthToken), roundTripper),
		})
	} else {
		client, err = api.NewClient(api.Config{
			Address: promAddress,
		})
	}

	if err != nil {
		log.Errorf("error creating prometheus client: %v", err)
		return nil, err
	}

	return promClient{
		client:     client,
		latestMode: latestMode,
		watchPod:   watchPod,
		watchNS:    watchNS,
		watchPodRx: watchPodRx,
		minimal:    minimal,
		useRules:   useRules,
		includeTS:  includeTS,
	}, err
}

func (s promClient) Name() string {
	return watcher.PromClientName
}

func (s promClient) FetchHostMetrics(host string, window *watcher.Window) ([]watcher.Metric, error) {
	var metricList []watcher.Metric
	var anyerr error

	var metrics []string
	if s.latestMode && s.minimal {
		// Minimal set for A1 agent
		if s.useRules {
			metrics = []string{
				ruleNodeCpuByNode,
				ruleNodePowerByNode,
				ruleNodeEnergyByNode,
			}
			if s.watchPod != "" || s.watchPodRx != "" {
				metrics = append(metrics,
					ruleAppCpuTorchServe,
					ruleAppPowerTorchServe,
					ruleAppEnergyTorchServe,
				)
				if s.includeTS {
					metrics = append(metrics, ruleTsLatencyMs, ruleTsThroughputRps)
				}
			}
		} else {
			metrics = []string{
				promCpuMetric,                         // node CPU
				promKeplerHostPlatformJoules,          // node power via rate
				promKeplerHostPlatformJoulesIncr1m,    // node energy via increase
			}
			if s.watchPod != "" || s.watchPodRx != "" {
				metrics = append(metrics,
					promContainerCpuRate1m,            // app CPU (pods)
					promKeplerContainerJoulesRate1m,   // app power (pods)
					promKeplerContainerJoulesIncr1m,   // app energy (pods)
				)
			}
		}
	} else {
		metrics = []string{promCpuMetric, promMemMetric, promTransBandMetric, promTransBandDropMetric,
			promRecBandMetric, promRecBandDropMetric, promDiskIOMetric, promScaphHostPower, promScaphHostJoules,
			promKeplerHostCoreJoules, promKeplerHostUncoreJoules, promKeplerHostDRAMJoules, promKeplerHostPackageJoules,
			promKeplerHostOtherJoules, promKeplerHostGPUJoules, promKeplerHostPlatformJoules, promKeplerHostEnergyStat}
	}

	if s.latestMode {
		for _, metric := range metrics {
			promQuery := s.buildLatestQuery(host, metric)
			promResults, err := s.getPromResults(promQuery)
			if err != nil {
				log.Errorf("error querying Prometheus for query %v: %v\n", promQuery, err)
				anyerr = err
				continue
			}
			curMetricMap := s.promResults2MetricMap(promResults, metric, promLatest, "1m")
			metricList = append(metricList, dedupMetrics(curMetricMap[host])...)
		}
		return metricList, anyerr
	}

	for _, method := range []string{promAvg, promStd} {
		for _, metric := range metrics {
			promQuery := s.buildPromQuery(host, metric, method, window.Duration)
			promResults, err := s.getPromResults(promQuery)

			if err != nil {
				log.Errorf("error querying Prometheus for query %v: %v\n", promQuery, err)
				anyerr = err
				continue
			}

			curMetricMap := s.promResults2MetricMap(promResults, metric, method, window.Duration)
			metricList = append(metricList, dedupMetrics(curMetricMap[host])...)
		}
	}

	return metricList, anyerr
}

// FetchAllHostsMetrics Fetch all host metrics with different operators (avg_over_time, stddev_over_time) and different resource types (CPU, Memory)
func (s promClient) FetchAllHostsMetrics(window *watcher.Window) (map[string][]watcher.Metric, error) {
	hostMetrics := make(map[string][]watcher.Metric)
	var anyerr error

	var metrics []string
	if s.latestMode && s.minimal {
		if s.useRules {
			metrics = []string{
				ruleNodeCpuByNode,
				ruleNodePowerByNode,
				ruleNodeEnergyByNode,
			}
			if s.watchPod != "" || s.watchPodRx != "" {
				metrics = append(metrics,
					ruleAppCpuTorchServe,
					ruleAppPowerTorchServe,
					ruleAppEnergyTorchServe,
				)
				if s.includeTS {
					metrics = append(metrics, ruleTsLatencyMs, ruleTsThroughputRps)
				}
			}
		} else {
			metrics = []string{
				promCpuMetric,
				promKeplerHostPlatformJoules,
				promKeplerHostPlatformJoulesIncr1m,
			}
			if s.watchPod != "" || s.watchPodRx != "" {
				metrics = append(metrics,
					promContainerCpuRate1m,
					promKeplerContainerJoulesRate1m,
					promKeplerContainerJoulesIncr1m,
				)
			}
		}
	} else {
		metrics = []string{promCpuMetric, promMemMetric, promTransBandMetric, promTransBandDropMetric,
			promRecBandMetric, promRecBandDropMetric, promDiskIOMetric, promScaphHostPower, promScaphHostJoules,
			promKeplerHostCoreJoules, promKeplerHostUncoreJoules, promKeplerHostDRAMJoules, promKeplerHostPackageJoules,
			promKeplerHostOtherJoules, promKeplerHostGPUJoules, promKeplerHostPlatformJoules, promKeplerHostEnergyStat}
	}

	if s.latestMode {
		for _, metric := range metrics {
			promQuery := s.buildLatestQuery(allHosts, metric)
			promResults, err := s.getPromResults(promQuery)
			if err != nil {
				log.Errorf("error querying Prometheus for query %v: %v\n", promQuery, err)
				anyerr = err
				continue
			}
			curMetricMap := s.promResults2MetricMap(promResults, metric, promLatest, "1m")
			for k, v := range curMetricMap {
				hostMetrics[k] = append(hostMetrics[k], dedupMetrics(v)...)
			}
		}
		return hostMetrics, anyerr
	}

	for _, method := range []string{promAvg, promStd} {
		for _, metric := range metrics {
			promQuery := s.buildPromQuery(allHosts, metric, method, window.Duration)
			promResults, err := s.getPromResults(promQuery)

			if err != nil {
				log.Errorf("error querying Prometheus for query %v: %v\n", promQuery, err)
				anyerr = err
				continue
			}

			curMetricMap := s.promResults2MetricMap(promResults, metric, method, window.Duration)

			for k, v := range curMetricMap {
				hostMetrics[k] = append(hostMetrics[k], dedupMetrics(v)...)
			}
		}
	}

	return hostMetrics, anyerr
}

func (s promClient) Health() (int, error) {
	req, err := http.NewRequest("HEAD", DefaultPromAddress, nil)
	if err != nil {
		return -1, err
	}
	resp, _, err := s.client.Do(context.Background(), req)
	if err != nil {
		return -1, err
	}
	if resp.StatusCode != http.StatusOK {
		return -1, fmt.Errorf("received response status code: %v", resp.StatusCode)
	}
	return 0, nil
}

func (s promClient) buildPromQuery(host string, metric string, method string, rollup string) string {
	var promQuery string

	if host == allHosts {
		promQuery = fmt.Sprintf("%s(%s[%s])", method, metric, rollup)
	} else {
		promQuery = fmt.Sprintf("%s(%s{%s=\"%s\"}[%s])", method, metric, hostMetricKey, host, rollup)
	}

	return promQuery
}

func (s promClient) buildLatestQuery(host string, metric string) string {
	// Special pseudo metrics
	switch metric {
	// Recording rule handling (node-level)
	case ruleNodeCpuByNode, ruleNodePowerByNode, ruleNodeEnergyByNode:
		if host == allHosts || host == "" {
			return metric
		}
		return fmt.Sprintf("%s{%s=\"%s\"}", metric, hostMetricKey, host)
	// Recording rule handling (app-level TorchServe)
	case ruleAppCpuTorchServe, ruleAppPowerTorchServe, ruleAppEnergyTorchServe:
		// Build OR between pod and pod_name label keys, include namespace if provided
		nsFilter := ""
		if s.watchNS != "" {
			nsFilter = fmt.Sprintf(",namespace=\"%s\"", s.watchNS)
		}
		podRe := s.watchPodRx
		if podRe == "" && s.watchPod != "" {
			podRe = "^" + s.watchPod + "$"
		}
		if podRe == "" {
			// No pod filter, return rule as-is
			return metric
		}
		left := fmt.Sprintf("%s{%s=~\"%s\"%s}", metric, "pod", podRe, nsFilter)
		right := fmt.Sprintf("%s{%s=~\"%s\"%s}", metric, "pod_name", podRe, nsFilter)
		return fmt.Sprintf("sum by (pod,instance) ((%s) or (%s))", left, right)
	// Recording rule handling (TorchServe TS metrics)
	case ruleTsLatencyMs, ruleTsThroughputRps:
		nsFilter := ""
		if s.watchNS != "" {
			nsFilter = fmt.Sprintf(",namespace=\"%s\"", s.watchNS)
		}
		podRe := s.watchPodRx
		if podRe == "" && s.watchPod != "" {
			podRe = "^" + s.watchPod + "$"
		}
		if podRe == "" {
			return metric
		}
		// TS usually uses label "pod"
		return fmt.Sprintf("%s{%s=~\"%s\"%s}", metric, "pod", podRe, nsFilter)
	case promKeplerHostPlatformJoulesIncr1m:
		if host == allHosts {
			return fmt.Sprintf("sum by (instance) (increase(%s[1m]))", promKeplerHostPlatformJoules)
		}
		return fmt.Sprintf("sum by (instance) (increase(%s{%s=\"%s\"}[1m]))", promKeplerHostPlatformJoules, hostMetricKey, host)
	case promContainerCpuRate1m:
		selector := s.selectorLabels(host, "")
		return fmt.Sprintf("sum by (pod,instance) (rate(container_cpu_usage_seconds_total%s[1m]))", selector)
	case promKeplerContainerJoulesRate1m:
		selector := s.selectorLabels(host, "")
		return fmt.Sprintf("sum by (pod,instance) (rate(kepler_container_joules_total%s[1m]))", selector)
	case promKeplerContainerJoulesIncr1m:
		selector := s.selectorLabels(host, "")
		return fmt.Sprintf("sum by (pod,instance) (increase(kepler_container_joules_total%s[1m]))", selector)
	}

	isCtr := isCounterMetric(metric)
	if host == allHosts {
		if isCtr {
			return fmt.Sprintf("sum by (instance) (rate(%s[1m]))", metric)
		}
		return metric
	}
	if isCtr {
		return fmt.Sprintf("sum by (instance) (rate(%s{%s=\"%s\"}[1m]))", metric, hostMetricKey, host)
	}
	return fmt.Sprintf("%s{%s=\"%s\"}", metric, hostMetricKey, host)
}

func (s promClient) selectorLabels(host string, extra string) string {
	labels := []string{}
	if host != allHosts && host != "" {
		labels = append(labels, fmt.Sprintf("%s=\"%s\"", hostMetricKey, host))
	}
	if s.watchNS != "" {
		labels = append(labels, fmt.Sprintf("%s=\"%s\"", "namespace", s.watchNS))
	}
	// Prefer regex if provided; else exact pod match if provided
	if s.watchPodRx != "" {
		labels = append(labels, fmt.Sprintf("%s=~\"%s\"", "pod", s.watchPodRx))
	} else if s.watchPod != "" {
		// Some metrics use label "pod" (k8s), others "pod_name" (older exporters). Prefer pod.
		labels = append(labels, fmt.Sprintf("%s=\"%s\"", "pod", s.watchPod))
	}
	if extra != "" {
		labels = append(labels, extra)
	}
	if len(labels) == 0 {
		return ""
	}
	return "{" + strings.Join(labels, ",") + "}"
}

func isCounterMetric(metric string) bool {
	return strings.HasSuffix(metric, "_joules_total") || metric == promScaphHostJoules
}

func (s promClient) getPromResults(promQuery string) (model.Value, error) {
	v1api := v1.NewAPI(s.client)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	results, warnings, err := v1api.Query(ctx, promQuery, time.Now())
	if err != nil {
		return nil, err
	}
	if len(warnings) > 0 {
		log.Warnf("Warnings: %v\n", warnings)
	}
	log.Debugf("result:\n%v\n", results)

	return results, nil
}

func (s promClient) promResults2MetricMap(promresults model.Value, metric string, method string, rollup string) map[string][]watcher.Metric {
	var metricType string
	var operator string

	curMetrics := make(map[string][]watcher.Metric)

	switch metric {
	case promCpuMetric: // CPU metrics
		metricType = watcher.CPU
	case promMemMetric: // Memory metrics
		metricType = watcher.Memory
	case promDiskIOMetric: // Storage metrics
		metricType = watcher.Storage
	case promScaphHostPower, promScaphHostJoules, // Energy-related metrics
		promKeplerHostCoreJoules, promKeplerHostUncoreJoules,
		promKeplerHostDRAMJoules, promKeplerHostPackageJoules,
		promKeplerHostOtherJoules, promKeplerHostGPUJoules,
		promKeplerHostPlatformJoules, promKeplerHostEnergyStat:
		metricType = watcher.Energy
	case promTransBandMetric, promTransBandDropMetric, // Bandwidth-related metrics
		promRecBandMetric, promRecBandDropMetric:
		metricType = watcher.Bandwidth
	default:
		// Heuristics for added pseudo metrics
		if strings.Contains(metric, "_joules") {
			metricType = watcher.Energy
		} else if strings.Contains(metric, "cpu") {
			metricType = watcher.CPU
		} else {
			metricType = watcher.Unknown
		}
	}

	if method == promAvg {
		operator = watcher.Average
	} else if method == promStd {
		operator = watcher.Std
	} else if method == promLatest {
		operator = watcher.Latest
	} else {
		operator = watcher.UnknownOperator
	}

	switch promresults.(type) {
	case model.Vector:
		for _, result := range promresults.(model.Vector) {
			// Pass through raw PromQL numeric value without scaling
			curMetric := watcher.Metric{Name: metric, Type: metricType, Operator: operator, Rollup: rollup, Value: float64(result.Value)}
			// Only add labels for app-level container metrics, not for node metrics
			if metric == promContainerCpuRate1m || metric == promKeplerContainerJoulesRate1m || metric == promKeplerContainerJoulesIncr1m {
				if podLbl, ok := result.Metric["pod"]; ok {
					if curMetric.Labels == nil {
						curMetric.Labels = make(map[string]string)
					}
					curMetric.Labels["pod"] = string(podLbl)
				}
				if nsLbl, ok := result.Metric["namespace"]; ok {
					if curMetric.Labels == nil {
						curMetric.Labels = make(map[string]string)
					}
					curMetric.Labels["namespace"] = string(nsLbl)
				}
			}
			curHost := string(result.Metric[hostMetricKey])
			curMetrics[curHost] = append(curMetrics[curHost], curMetric)
		}
	default:
		log.Errorf("error: The Prometheus results should not be type: %v.\n", promresults.Type())
	}

	return curMetrics
}

// dedupMetrics removes duplicates by (name,pod) key within a slice.
func dedupMetrics(in []watcher.Metric) []watcher.Metric {
	if len(in) <= 1 {
		return in
	}
	seen := make(map[string]struct{}, len(in))
	out := make([]watcher.Metric, 0, len(in))
	for _, m := range in {
		key := m.Name
		if m.Labels != nil {
			if pod, ok := m.Labels["pod"]; ok {
				key += "|pod=" + pod
			}
		}
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		out = append(out, m)
	}
	return out
}
