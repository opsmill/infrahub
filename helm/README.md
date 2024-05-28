# Infrahub Helm Chart

## Description

This Helm chart deploys Infrahub on Kubernetes. It provides configurable templates for various Kubernetes resources including caching, databases, and message queues, ensuring a scalable and efficient deployment of the Infrahub application.

## Chart Structure

The chart includes the following files and directories:

- `Chart.yaml`: Chart metadata file.
- `templates/`: Contains the template files for Kubernetes resources.
  - `_helpers.tpl`: Template helpers/definitions.
  - `cache.yaml`: Defines the cache (Redis) deployment, service, and PVC.
  - `message-queue-configmap.yaml`: ConfigMap for RabbitMQ configuration.
  - `database.yaml`: Database (Neo4j) deployment, service, and PVC.
  - `infrahub-git.yaml`: Infrahub Git service deployment and service.
  - `infrahub-server-db-init-job.yaml`: Initialization jobs for Infrahub Server.
  - `infrahub-server-demo-data-job.yaml`: Job that loads demo dataset to Infrahub.
  - `infrahub-server-ingress.yaml`: Ingress configuration for Infrahub Server.
  - `infrahub-server.yaml`: Infrahub Server deployment and service.
  - `message-queue.yaml`: Message Queue (RabbitMQ) deployment and service.
- `values.yaml`: Defines configuration values for the chart.

## Infrahub Configuration

The Infrahub configuration is structured as follows:

- The `internal_address` is dynamically set based on the release name, namespace, and cluster domain.
- Database, broker, cache, and other service addresses are set dynamically, referring to the relevant services within the Kubernetes cluster.
- Ports for services like the database and cache are pulled from the `values.yaml` file, ensuring flexibility and ease of configuration changes.

Using environment variables is also possible and recommended to set or override existing configuration values.

It is possible to use Kubernetes secrets to configure credentials required by Infrahub such as the database credentials.
The `envFromExistingSecret` parameter is available to pass environment variables from Kubernetes secrets.

## Prerequisites

- Kubernetes 1.12+
- Helm 3.0+
- PV provisioner support in the underlying infrastructure (if persistence is required)

## Installing the Chart

To install the chart with the release name `infrahub`:

```sh
helm install infrahub path/to/infrahub/chart
```

## Configuration

The following table lists the configurable parameters in the `values.yaml` file and their default values.

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| `global.kubernetesClusterDomain` | Kubernetes cluster domain | `cluster.local`  |
| `global.imageRegistry` | Image registry for pulling images | `registry.opsmill.io`  |
| `global.infrahubRepository` | Repository for Infrahub images | `opsmill/infrahub-py3.11`  |
| `global.infrahubTag` | Tag for Infrahub images | `0.14.0`  |
| `global.imagePullPolicy` | Default image pull policy | `IfNotPresent`  |
| `cache.type` | Service type for cache | `ClusterIP`  |
| `cache.cache.image.repository` | The Redis image repository | `redis` |
| `cache.cache.image.tag` | The Redis image tag | `"7.2"` |
| `database.type` | Service type for cache | `ClusterIP`  |
| `database.database.image.repository` | The Neo4j image repository | `neo4j` |
| `database.database.image.tag` | The Neo4j image tag | `5.13-community` |
| `messageQueue.messageQueue.image.repository` | The RabbitMQ image repository | `rabbitmq` |
| `messageQueue.messageQueue.image.tag` | The RabbitMQ image tag | `3.12-management` |
| ... | ... | ... |

For more detailed configuration and additional parameters, refer to the `values.yaml` file.

## Upgrading the Chart

To upgrade the chart to a new version:

```sh
helm upgrade infrahub path/to/infrahub/chart
```

## Uninstalling the Chart

To uninstall/delete the `infrahub` deployment:

```sh
helm delete infrahub
```

## Persistence

The chart offers the ability to configure persistence for the database and other components. Check the `persistence` section of each component in `values.yaml` for more details.

## Customization

The chart is customizable through `values.yaml`. For more complex customizations and usage scenarios, refer to the official Helm documentation.
