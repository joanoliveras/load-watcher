package exporter

import (
	"net/http"

	"github.com/paypal/load-watcher/pkg/watcher"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	observedGauge = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "loadwatcher_observed_value",
			Help: "Observed metric value from load-watcher cache.",
		},
		[]string{"host", "name", "type", "operator", "window"},
	)
)

func init() {
	prometheus.MustRegister(observedGauge)
}

// RegisterHandlers registers the /metrics endpoint on the default HTTP mux.
func RegisterHandlers() {
	http.Handle("/metrics", promhttp.Handler())
}

// UpdateObserved publishes the latest observed metrics snapshot into Prometheus gauges.
func UpdateObserved(metrics *watcher.WatcherMetrics) {
	window := metrics.Window.Duration
	for host, node := range metrics.Data.NodeMetricsMap {
		for _, m := range node.Metrics {
			observedGauge.With(prometheus.Labels{
				"host":     host,
				"name":     m.Name,
				"type":     m.Type,
				"operator": m.Operator,
				"window":   window,
			}).Set(m.Value)
		}
	}
}


