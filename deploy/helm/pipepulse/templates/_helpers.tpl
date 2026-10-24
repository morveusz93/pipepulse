{{- define "pipepulse.fullname" -}}
{{- if contains .Chart.Name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "pipepulse.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "pipepulse.selector" -}}
app.kubernetes.io/name: {{ .root.Chart.Name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "pipepulse.image" -}}
{{ .root.Values.image.repository }}/{{ .name }}:{{ .root.Values.image.tag }}
{{- end -}}

{{- define "pipepulse.secretName" -}}
{{- .Values.secrets.existingSecret | default (printf "%s-app" (include "pipepulse.fullname" .)) -}}
{{- end -}}

{{/* Env shared by api, worker and jobs: database, encryption, mode and poller settings. */}}
{{- define "pipepulse.backendEnv" -}}
{{- $fullname := include "pipepulse.fullname" . }}
{{- if .Values.postgres.enabled }}
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ $fullname }}-postgres
      key: password
- name: PIPEPULSE_DATABASE_URL
  value: "postgresql+psycopg://pipepulse:$(POSTGRES_PASSWORD)@{{ $fullname }}-postgres:5432/pipepulse"
{{- else }}
- name: PIPEPULSE_DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "pipepulse.secretName" . }}
      key: database-url
{{- end }}
- name: PIPEPULSE_ENCRYPTION_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "pipepulse.secretName" . }}
      key: encryption-key
      optional: true
- name: PIPEPULSE_ADMIN_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "pipepulse.secretName" . }}
      key: admin-password
      optional: true
- name: PIPEPULSE_DEMO_MODE
  value: {{ .Values.demo.enabled | quote }}
- name: PIPEPULSE_POLL_INTERVAL_SECONDS
  value: {{ .Values.config.pollIntervalSeconds | quote }}
- name: PIPEPULSE_BACKFILL_DAYS
  value: {{ .Values.config.backfillDays | quote }}
- name: PIPEPULSE_TRACE_TAIL_LINES
  value: {{ .Values.config.traceTailLines | quote }}
{{- end -}}

{{- define "pipepulse.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
fsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "pipepulse.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}
