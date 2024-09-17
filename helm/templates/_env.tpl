{{/*
Define default env variables if required.
*/}}
{{- define "infrahub-helm.infrahubDemoData.defaultEnv" -}}
{{- if not .Values.infrahubDemoData.env.KUBERNETES_CLUSTER_DOMAIN }}
- name: KUBERNETES_CLUSTER_DOMAIN
  value: {{ quote .Values.global.kubernetesClusterDomain }}
{{- end }}
{{- if not .Values.infrahubDemoData.env.INFRAHUB_ADDRESS }}
- name: INFRAHUB_ADDRESS
  value: http://{{ include "infrahub-helm.fullname" . }}-infrahub-server.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}:8000
{{- end }}
{{- if not .Values.infrahubDemoData.env.INFRAHUB_INTERNAL_ADDRESS }}
- name: INFRAHUB_INTERNAL_ADDRESS
  value: "http://{{ include "infrahub-helm.fullname" . }}-infrahub-server.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}:8000"
{{- end }}
{{- if not .Values.infrahubDemoData.env.INFRAHUB_DB_ADDRESS }}
- name: INFRAHUB_DB_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-database.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubDemoData.env.INFRAHUB_DB_PORT }}
- name: INFRAHUB_DB_PORT
  value: "{{ .Values.neo4j.services.neo4j.ports.bolt.port }}"
{{- end }}
{{- if not .Values.infrahubDemoData.env.INFRAHUB_BROKER_ADDRESS }}
- name: INFRAHUB_BROKER_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-message-queue.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubDemoData.env.INFRAHUB_BROKER_USERNAME }}
- name: INFRAHUB_BROKER_USERNAME
  value: {{ .Values.rabbitmq.auth.username | quote }}
{{- end }}
{{- if not .Values.infrahubDemoData.env.INFRAHUB_BROKER_PASSWORD }}
- name: INFRAHUB_BROKER_PASSWORD
  value: {{ .Values.rabbitmq.auth.password | quote }}
{{- end }}
{{- if not .Values.infrahubDemoData.env.INFRAHUB_CACHE_ADDRESS }}
- name: INFRAHUB_CACHE_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-cache-master.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubDemoData.env.INFRAHUB_CACHE_PORT }}
- name: INFRAHUB_CACHE_PORT
  value: "{{ .Values.redis.master.service.ports.redis }}"
{{- end }}
{{- end }}

{{- define "infrahub-helm.infrahubServer.defaultEnv" -}}
{{- if not .Values.infrahubServer.infrahubServer.env.KUBERNETES_CLUSTER_DOMAIN }}
- name: KUBERNETES_CLUSTER_DOMAIN
  value: {{ quote .Values.global.kubernetesClusterDomain }}
{{- end }}
{{- if not .Values.infrahubServer.infrahubServer.env.INFRAHUB_ADDRESS }}
- name: INFRAHUB_ADDRESS
  value: http://{{ include "infrahub-helm.fullname" . }}-infrahub-server.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}:8000
{{- end }}
{{- if not .Values.infrahubServer.infrahubServer.env.INFRAHUB_INTERNAL_ADDRESS }}
- name: INFRAHUB_INTERNAL_ADDRESS
  value: "http://{{ include "infrahub-helm.fullname" . }}-infrahub-server.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}:8000"
{{- end }}
{{- if not .Values.infrahubServer.infrahubServer.env.INFRAHUB_DB_ADDRESS }}
- name: INFRAHUB_DB_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-database.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubServer.infrahubServer.env.INFRAHUB_DB_PORT }}
- name: INFRAHUB_DB_PORT
  value: "{{ .Values.neo4j.services.neo4j.ports.bolt.port }}"
{{- end }}
{{- if not .Values.infrahubServer.infrahubServer.env.INFRAHUB_BROKER_ADDRESS }}
- name: INFRAHUB_BROKER_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-message-queue.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubServer.infrahubServer.env.INFRAHUB_BROKER_USERNAME }}
- name: INFRAHUB_BROKER_USERNAME
  value: {{ .Values.rabbitmq.auth.username | quote }}
{{- end }}
{{- if not .Values.infrahubServer.infrahubServer.env.INFRAHUB_BROKER_PASSWORD }}
- name: INFRAHUB_BROKER_PASSWORD
  value: {{ .Values.rabbitmq.auth.password | quote }}
{{- end }}
{{- if not .Values.infrahubServer.infrahubServer.env.INFRAHUB_CACHE_ADDRESS }}
- name: INFRAHUB_CACHE_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-cache-master.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubServer.infrahubServer.env.INFRAHUB_CACHE_PORT }}
- name: INFRAHUB_CACHE_PORT
  value: "{{ .Values.redis.master.service.ports.redis }}"
{{- end }}
{{- end }}

{{- define "infrahub-helm.infrahubGit.defaultEnv" -}}
{{- if not .Values.infrahubGit.infrahubGit.env.KUBERNETES_CLUSTER_DOMAIN }}
- name: KUBERNETES_CLUSTER_DOMAIN
  value: {{ quote .Values.global.kubernetesClusterDomain }}
{{- end }}
{{- if not .Values.infrahubGit.infrahubGit.env.INFRAHUB_ADDRESS }}
- name: INFRAHUB_ADDRESS
  value: http://{{ include "infrahub-helm.fullname" . }}-infrahub-server.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}:8000
{{- end }}
{{- if not .Values.infrahubGit.infrahubGit.env.INFRAHUB_INTERNAL_ADDRESS }}
- name: INFRAHUB_INTERNAL_ADDRESS
  value: "http://{{ include "infrahub-helm.fullname" . }}-infrahub-server.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}:8000"
{{- end }}
{{- if not .Values.infrahubGit.infrahubGit.env.INFRAHUB_DB_ADDRESS }}
- name: INFRAHUB_DB_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-database.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubGit.infrahubGit.env.INFRAHUB_DB_PORT }}
- name: INFRAHUB_DB_PORT
  value: "{{ .Values.neo4j.services.neo4j.ports.bolt.port }}"
{{- end }}
{{- if not .Values.infrahubGit.infrahubGit.env.INFRAHUB_BROKER_ADDRESS }}
- name: INFRAHUB_BROKER_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-message-queue.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubGit.infrahubGit.env.INFRAHUB_BROKER_USERNAME }}
- name: INFRAHUB_BROKER_USERNAME
  value: {{ .Values.rabbitmq.auth.username | quote }}
{{- end }}
{{- if not .Values.infrahubGit.infrahubGit.env.INFRAHUB_BROKER_PASSWORD }}
- name: INFRAHUB_BROKER_PASSWORD
  value: {{ .Values.rabbitmq.auth.password | quote }}
{{- end }}
{{- if not .Values.infrahubGit.infrahubGit.env.INFRAHUB_CACHE_ADDRESS }}
- name: INFRAHUB_CACHE_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-cache-master.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubGit.infrahubGit.env.INFRAHUB_CACHE_PORT }}
- name: INFRAHUB_CACHE_PORT
  value: "{{ .Values.redis.master.service.ports.redis }}"
{{- end }}
{{- end }}

{{- define "infrahub-helm.infrahubTaskRunner.defaultEnv" -}}
{{- if not .Values.infrahubTaskRunner.infrahubTaskRunner.env.KUBERNETES_CLUSTER_DOMAIN }}
- name: KUBERNETES_CLUSTER_DOMAIN
  value: {{ quote .Values.global.kubernetesClusterDomain }}
{{- end }}
{{- if not .Values.infrahubTaskRunner.infrahubTaskRunner.env.INFRAHUB_ADDRESS }}
- name: INFRAHUB_ADDRESS
  value: http://{{ include "infrahub-helm.fullname" . }}-infrahub-server.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}:8000
{{- end }}
{{- if not .Values.infrahubTaskRunner.infrahubTaskRunner.env.INFRAHUB_INTERNAL_ADDRESS }}
- name: INFRAHUB_INTERNAL_ADDRESS
  value: "http://{{ include "infrahub-helm.fullname" . }}-infrahub-server.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}:8000"
{{- end }}
{{- if not .Values.infrahubTaskRunner.infrahubTaskRunner.env.INFRAHUB_DB_ADDRESS }}
- name: INFRAHUB_DB_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-database.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubTaskRunner.infrahubTaskRunner.env.INFRAHUB_DB_PORT }}
- name: INFRAHUB_DB_PORT
  value: "{{ .Values.neo4j.services.neo4j.ports.bolt.port }}"
{{- end }}
{{- if not .Values.infrahubTaskRunner.infrahubTaskRunner.env.INFRAHUB_BROKER_ADDRESS }}
- name: INFRAHUB_BROKER_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-message-queue.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubTaskRunner.infrahubTaskRunner.env.INFRAHUB_BROKER_USERNAME }}
- name: INFRAHUB_BROKER_USERNAME
  value: {{ .Values.rabbitmq.auth.username | quote }}
{{- end }}
{{- if not .Values.infrahubTaskRunner.infrahubTaskRunner.env.INFRAHUB_BROKER_PASSWORD }}
- name: INFRAHUB_BROKER_PASSWORD
  value: {{ .Values.rabbitmq.auth.password | quote }}
{{- end }}
{{- if not .Values.infrahubTaskRunner.infrahubTaskRunner.env.INFRAHUB_CACHE_ADDRESS }}
- name: INFRAHUB_CACHE_ADDRESS
  value: "{{ include "infrahub-helm.fullname" . }}-cache-master.{{ .Release.Namespace }}.svc.{{ .Values.global.kubernetesClusterDomain }}"
{{- end }}
{{- if not .Values.infrahubTaskRunner.infrahubTaskRunner.env.INFRAHUB_CACHE_PORT }}
- name: INFRAHUB_CACHE_PORT
  value: "{{ .Values.redis.master.service.ports.redis }}"
{{- end }}
{{- end }}
