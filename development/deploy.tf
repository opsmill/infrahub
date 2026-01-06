terraform {
  required_providers {
    kubectl = {
      source  = "alekc/kubectl"
      version = "2.1.3"
    }
  }
}

provider "helm" {
  kubernetes = {
    config_path = "~/.kube/config"
  }
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

provider "kubectl" {
  config_path = "~/.kube/config"
}

locals {
  target_namespace = "infrahub"
  infrahub_version = "1.4.10"
}

### Infrahub

resource "helm_release" "infrahub_ha" {
  depends_on = [helm_release.taskmanager_ha, helm_release.cache_ha, helm_release.messagequeue_ha, helm_release.database_ha, helm_release.objectstore_ha]

  name    = "infrahub"
  chart   = "oci://registry.opsmill.io/opsmill/chart/infrahub-enterprise"
  version = "3.9.4"

  create_namespace = true
  namespace        = local.target_namespace

  values = [
    <<EOT
infrahub:
  global:
    infrahubTag: ${local.infrahub_version}
  infrahubServer:
    replicas: 3
    persistence:
      enabled: false
    infrahubServer:
      env:
        INFRAHUB_DB_ADDRESS: infrahub-headless.${local.target_namespace}.svc.cluster.local # use FQDN to match neo4j's Helm cluster domain so that client-side routing is used
        INFRAHUB_DB_PROTOCOL: neo4j # required for client-side routing
        INFRAHUB_BROKER_ADDRESS: messagequeue-rabbitmq
        INFRAHUB_CACHE_ADDRESS: redis-sentinel-proxy
        INFRAHUB_CACHE_PORT: 6379
        INFRAHUB_WORKFLOW_ADDRESS: prefect-server
        INFRAHUB_WORKFLOW_PORT: 4200
        PREFECT_API_URL: "http://prefect-server:4200/api"

        INFRAHUB_STORAGE_DRIVER: s3
        AWS_ACCESS_KEY_ID: admin
        AWS_SECRET_ACCESS_KEY: password
        AWS_S3_BUCKET_NAME: infrahub-data
        AWS_S3_ENDPOINT_URL: objectstore-minio:9000
        AWS_S3_USE_SSL: "false"

        INFRAHUB_ALLOW_ANONYMOUS_ACCESS: "true"
        INFRAHUB_DB_TYPE: neo4j
        INFRAHUB_LOG_LEVEL: INFO
        INFRAHUB_PRODUCTION: "false"
        INFRAHUB_INITIAL_ADMIN_TOKEN: 06438eb2-8019-4776-878c-0941b1f1d1ec
        INFRAHUB_SECURITY_SECRET_KEY: 327f747f-efac-42be-9e73-999f08f86b92
        INFRAHUB_GIT_REPOSITORIES_DIRECTORY: "/opt/infrahub/git"
    affinity:
      podAntiAffinity:
        requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchLabels:
                service: infrahub-server
            topologyKey: kubernetes.io/hostname
  infrahubTaskWorker:
    replicas: 3
    infrahubTaskWorker:
      env:
        INFRAHUB_DB_ADDRESS: infrahub-headless.${local.target_namespace}.svc.cluster.local # use FQDN to match neo4j's Helm cluster domain so that client-side routing is used
        INFRAHUB_DB_PROTOCOL: neo4j # required for client-side routing
        INFRAHUB_BROKER_ADDRESS: messagequeue-rabbitmq
        INFRAHUB_CACHE_ADDRESS: redis-sentinel-proxy
        INFRAHUB_CACHE_PORT: 6379
        INFRAHUB_WORKFLOW_ADDRESS: prefect-server
        INFRAHUB_WORKFLOW_PORT: 4200
        PREFECT_API_URL: "http://prefect-server:4200/api"

        INFRAHUB_STORAGE_DRIVER: s3
        AWS_ACCESS_KEY_ID: admin
        AWS_SECRET_ACCESS_KEY: password
        AWS_S3_BUCKET_NAME: infrahub-data
        AWS_S3_ENDPOINT_URL: objectstore-minio:9000
        AWS_S3_USE_SSL: "false"

        INFRAHUB_DB_TYPE: neo4j
        INFRAHUB_LOG_LEVEL: DEBUG
        INFRAHUB_PRODUCTION: "false"
        INFRAHUB_API_TOKEN: 06438eb2-8019-4776-878c-0941b1f1d1ec
        INFRAHUB_TIMEOUT: "60"
        INFRAHUB_GIT_REPOSITORIES_DIRECTORY: "/opt/infrahub/git"
        PREFECT_WORKER_QUERY_SECONDS: 3
        PREFECT_AGENT_QUERY_INTERVAL: 3
    affinity:
      podAntiAffinity:
        requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchLabels:
                service: infrahub-task-worker
            topologyKey: kubernetes.io/hostname
  redis:
    enabled: false
  neo4j:
    enabled: false
  rabbitmq:
    enabled: false
  prefect-server:
    enabled: false
EOT
  ]
}

#### Infrahub dependencies

resource "helm_release" "database_ha_service" {
  depends_on = [helm_release.database_ha]

  name       = "database-service"
  chart      = "neo4j-headless-service"
  repository = "https://helm.neo4j.com/neo4j/"
  version    = "2025.3.0"

  create_namespace = true
  namespace        = local.target_namespace

  values = [
    <<EOT
neo4j:
  name: "infrahub"
EOT
  ]
}

resource "helm_release" "database_ha" {
  depends_on = [kubernetes_secret_v1.neo4j_secret]

  count = 3

  name       = "database-${count.index}"
  chart      = "neo4j"
  repository = "https://helm.neo4j.com/neo4j/"
  version    = "2025.3.0"

  create_namespace = true
  namespace        = local.target_namespace

  values = [
    <<EOT
neo4j:
  name: "infrahub"
  minimumClusterSize: 3
  resources:
    cpu: "4"
    memory: "8Gi"
  passwordFromSecret: "neo4j-user"
  edition: "enterprise"
  acceptLicenseAgreement: "yes"
config:
  dbms.security.auth_minimum_password_length: "4"
  dbms.security.procedures.unrestricted: apoc.*
logInitialPassword: false
volumes:
  data:
    mode: "defaultStorageClass"
    defaultStorageClass:
      accessModes:
        - ReadWriteOnce
      requests:
        storage: 10Gi
services:
  neo4j:
    enabled: false
EOT
  ]
}

resource "helm_release" "messagequeue_ha" {
  name    = "messagequeue"
  chart   = "oci://registry-1.docker.io/bitnamicharts/rabbitmq"
  version = "14.4.1"

  create_namespace = true
  namespace        = local.target_namespace

  values = [
    <<EOT
replicaCount: 3
image:
  repository: bitnamilegacy/rabbitmq
auth:
  username: infrahub
  password: infrahub
metrics:
  enabled: true
startupProbe:
  enabled: true
podAntiAffinityPreset: hard
EOT
  ]
}

resource "helm_release" "objectstore_ha" {
  name    = "objectstore"
  chart   = "oci://registry-1.docker.io/bitnamicharts/minio"
  version = "15.0.5"

  create_namespace = true
  namespace        = local.target_namespace

  values = [
    <<EOT
global:
  security:
    allowInsecureImages: true
image:
  repository: bitnamilegacy/minio
mode: distributed
statefulset:
  replicaCount: 3
  drivesPerNode: 2
auth:
  rootUser: admin
  rootPassword: password
provisioning:
  enabled: true
  buckets:
    - name: infrahub-data
podAntiAffinityPreset: hard
volumePermissions:
  image:
    repository:	bitnamilegacy/os-shell
EOT
  ]
}

#### Task manager

resource "helm_release" "taskmanager_ha" {
  depends_on = [helm_release.cache_ha, kubectl_manifest.taskmanagerdb_ha]

  name       = "taskmanager"
  chart      = "prefect-server"
  repository = "https://prefecthq.github.io/prefect-helm"
  version    = "2025.7.31204438"

  create_namespace = true
  namespace        = local.target_namespace

  values = [
    <<EOT
global:
  prefect:
    image:
      repository: registry.opsmill.io/opsmill/infrahub-enterprise
      prefectTag: ${local.infrahub_version}
server:
  replicaCount: 3
  command:
    - /usr/bin/tini
    - -g
    - --
  args:
    - gunicorn
    - -k
    - uvicorn.workers.UvicornWorker
    - -b
    - 0.0.0.0:4200
    - 'infrahub.prefect_server.app:create_infrahub_prefect()'
  env:
    - name: INFRAHUB_CACHE_ADDRESS
      value: redis-sentinel-proxy
    - name: PREFECT_UI_SERVE_BASE
      value: /
    - name: PREFECT__SERVER_WEBSERVER_ONLY
      value: "true"
    - name: PREFECT_MESSAGING_BROKER
      value: prefect_redis.messaging
    - name: PREFECT_MESSAGING_CACHE
      value: prefect_redis.messaging
    - name: PREFECT_SERVER_EVENTS_CAUSAL_ORDERING
      value: prefect_redis.ordering
    - name: PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE
      value: prefect_redis.lease_storage
    - name: PREFECT_REDIS_MESSAGING_HOST
      value: redis-sentinel-proxy
    - name: PREFECT_REDIS_MESSAGING_DB
      value: "1"
    - name: PREFECT_API_DATABASE_MIGRATE_ON_START
      value: "false"
    - name: PREFECT_API_BLOCKS_REGISTER_ON_START
      value: "false"
  podSecurityContext:
    runAsUser: 1000
    fsGroup: 1000
  containerSecurityContext:
    runAsUser: 1000
    readOnlyRootFilesystem: false
secret:
  create: true
  name: ""
  username: "prefect"
  password: "prefect"
  host: "taskmanagerdb-rw"
  port: "5432"
  database: "prefect"
serviceAccount:
  create: false
postgresql:
  enabled: false
EOT
  ]
}

resource "kubernetes_service_v1" "redis_sentinel_proxy_svc" {
  depends_on = [helm_release.cache_ha]

  metadata {
    name      = "redis-sentinel-proxy"
    namespace = local.target_namespace
    labels = {
      "app.kubernetes.io/name" = "redis-sentinel-proxy"
    }
  }

  spec {
    type = "ClusterIP"
    port {
      port        = 6379
      target_port = "redis"
      name        = "cache-ha"
    }
    selector = {
      "app.kubernetes.io/name" = "redis-sentinel-proxy"
    }
  }
}

resource "kubernetes_deployment_v1" "redis_sentinel_proxy_deployment" {
  depends_on = [helm_release.cache_ha]

  metadata {
    name      = "redis-sentinel-proxy"
    namespace = local.target_namespace
    labels = {
      "app.kubernetes.io/name" = "redis-sentinel-proxy"
    }
  }

  spec {
    replicas = 2
    selector {
      match_labels = {
        "app.kubernetes.io/name" = "redis-sentinel-proxy"
      }
    }
    template {
      metadata {
        labels = {
          "app.kubernetes.io/name" = "redis-sentinel-proxy"
        }
      }
      spec {
        affinity {
          pod_anti_affinity {
            required_during_scheduling_ignored_during_execution {
              label_selector {
                match_labels = {
                  "app.kubernetes.io/name" = "redis-sentinel-proxy"
                }
              }
              topology_key = "kubernetes.io/hostname"
            }
          }
        }
        container {
          name  = "redis-sentinel-proxy"
          image = "patrickdk/redis-sentinel-proxy:v1.2"
          args = [
            "-master",
            "mymaster",
            "-listen",
            ":6379",
            "-sentinel",
            "cache:26379",
          ]
          port {
            container_port = 6379
            name           = "redis"
          }
        }
      }
    }
  }
}

resource "helm_release" "cache_ha" {
  name       = "cache"
  chart      = "redis"
  repository = "https://charts.bitnami.com/bitnami"
  version    = "19.5.2"

  create_namespace = true
  namespace        = local.target_namespace

  values = [
    <<EOT
nameOverride: cache
image:
  repository: bitnamilegacy/redis
architecture: replication
auth:
  enabled: false
master:
  podAntiAffinityPreset: hard
  persistence:
    enabled: true
  service:
    ports:
      redis: 6379
replicas:
  replicaCount: 3
  podAntiAffinityPreset: hard
sentinel:
  enabled: true
  image:
    repository: bitnamilegacy/redis-sentinel
EOT
  ]
}

resource "kubectl_manifest" "taskmanagerdb_ha" {
  depends_on = [helm_release.taskmanagerdb_ha_operator, kubernetes_secret_v1.db_secret]

  yaml_body = <<EOT
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: taskmanagerdb
  namespace: ${local.target_namespace}
spec:
  instances: 3
  storage:
    size: 10Gi
  postgresql:
    pg_hba:
      - host all all 10.0.0.0/8 md5
  bootstrap:
    initdb:
      database: prefect
      owner: prefect
      secret:
        name: prefect-user
EOT
}

resource "kubernetes_secret_v1" "db_secret" {
  depends_on = [helm_release.taskmanagerdb_ha_operator]

  metadata {
    name      = "prefect-user"
    namespace = local.target_namespace
  }
  data = {
    username = "prefect"
    password = "prefect"
  }
}

resource "kubernetes_secret_v1" "neo4j_secret" {
  metadata {
    name      = "neo4j-user"
    namespace = local.target_namespace
  }
  data = {
    NEO4J_AUTH = "neo4j/admin"
  }
}

resource "helm_release" "taskmanagerdb_ha_operator" {
  name       = "cnpg"
  chart      = "cloudnative-pg"
  repository = "https://cloudnative-pg.github.io/charts"
  version    = "0.23.2"

  create_namespace = true
  namespace        = local.target_namespace

  values = [
    <<EOT
EOT
  ]
}
