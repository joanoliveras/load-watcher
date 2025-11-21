/*
Copyright 2020 PayPal

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

package main

import (
	"time"
	
	"github.com/paypal/load-watcher/pkg/exporter"
	"github.com/paypal/load-watcher/pkg/watcher"
	"github.com/paypal/load-watcher/pkg/watcher/api"
	log "github.com/sirupsen/logrus"
	"os"
)

func init() {
	log.SetReportCaller(true)
	logLevel, evnLogLevelSet := os.LookupEnv("LOG_LEVEL")
	parsedLogLevel, err := log.ParseLevel(logLevel)
	if evnLogLevelSet && err != nil {
		log.Infof("unable to parse log level set; defaulting to: %v", log.GetLevel())
	}
	if err == nil {
		log.SetLevel(parsedLogLevel)
	}
}

func main() {
	client, err := api.NewLibraryClient(watcher.EnvMetricProviderOpts)
	if err != nil {
		log.Fatalf("unable to create client: %v", err)
	}

	// Register Prometheus exporter endpoint
	exporter.RegisterHandlers()

	// Periodically publish observed metrics to /metrics
	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()
		for {
			metrics, err := client.GetLatestWatcherMetrics()
			if err == nil && metrics != nil {
				exporter.UpdateObserved(metrics)
			} else if err != nil {
				log.Debugf("exporter skipped update: %v", err)
			}
			<-ticker.C
		}
	}()

	// Keep the watcher server up
	select {}
}
