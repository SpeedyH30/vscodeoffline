{{/*
Expand the name of the chart.
*/}}
{{- define "vscode-offline.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "vscode-offline.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "vscode-offline.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "vscode-offline.labels" -}}
helm.sh/chart: {{ include "vscode-offline.chart" . }}
{{ include "vscode-offline.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "vscode-offline.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vscode-offline.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Gallery selector labels
*/}}
{{- define "vscode-offline.gallerySelectorLabels" -}}
{{ include "vscode-offline.selectorLabels" . }}
app.kubernetes.io/component: gallery
{{- end }}

{{/*
Sync selector labels
*/}}
{{- define "vscode-offline.syncSelectorLabels" -}}
{{ include "vscode-offline.selectorLabels" . }}
app.kubernetes.io/component: sync
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "vscode-offline.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "vscode-offline.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Image pull secrets
*/}}
{{- define "vscode-offline.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Storage class helper
*/}}
{{- define "vscode-offline.storageClass" -}}
{{- if .Values.global.storageClass }}
{{- .Values.global.storageClass }}
{{- else }}
{{- .storageClass }}
{{- end }}
{{- end }}