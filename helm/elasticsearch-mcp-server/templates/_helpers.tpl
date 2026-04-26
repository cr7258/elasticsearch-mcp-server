{{/*
Expand the name of the chart.
*/}}
{{- define "elasticsearch-mcp-server.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "elasticsearch-mcp-server.fullname" -}}
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
Create chart label value.
*/}}
{{- define "elasticsearch-mcp-server.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "elasticsearch-mcp-server.labels" -}}
helm.sh/chart: {{ include "elasticsearch-mcp-server.chart" . }}
{{ include "elasticsearch-mcp-server.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "elasticsearch-mcp-server.selectorLabels" -}}
app.kubernetes.io/name: {{ include "elasticsearch-mcp-server.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use.
*/}}
{{- define "elasticsearch-mcp-server.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "elasticsearch-mcp-server.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Name of the Secret containing credentials.
Returns the existing secret name if provided, otherwise the chart-managed secret name.
*/}}
{{- define "elasticsearch-mcp-server.secretName" -}}
{{- if .Values.auth.existingSecret }}
{{- .Values.auth.existingSecret }}
{{- else }}
{{- include "elasticsearch-mcp-server.fullname" . }}
{{- end }}
{{- end }}

{{/*
Resolve the MCP server URL path.
Falls back to the transport-appropriate default when server.path is empty.
*/}}
{{- define "elasticsearch-mcp-server.serverPath" -}}
{{- if .Values.server.path }}
{{- .Values.server.path }}
{{- else if eq .Values.server.transport "sse" }}
{{- "/sse" }}
{{- else }}
{{- "/mcp" }}
{{- end }}
{{- end }}
