{{/*
Chart name, truncated/sanitized for use in resource names.
*/}}
{{- define "kavach.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully qualified release name, e.g. "myrelease-kavach".
*/}}
{{- define "kavach.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Standard labels applied to every resource.
*/}}
{{- define "kavach.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{ include "kavach.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Base selector labels — component-specific templates append
app.kubernetes.io/component themselves.
*/}}
{{- define "kavach.selectorLabels" -}}
app.kubernetes.io/name: {{ include "kavach.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Name of the Secret every workload's envFrom points at — either the
chart-managed one or an operator-supplied existingSecret.
*/}}
{{- define "kavach.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-secrets" (include "kavach.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/*
Name of the app ConfigMap.
*/}}
{{- define "kavach.configMapName" -}}
{{- printf "%s-config" (include "kavach.fullname" .) -}}
{{- end -}}

{{/*
Postgres DATABASE_URL, built from the in-chart Postgres service — only
meaningful when postgres.enabled is true. When it's false, set
config.databaseUrl (via an existing Secret) to point at an external DB
instead; see secret.yaml.
*/}}
{{- define "kavach.postgresHost" -}}
{{- printf "%s-postgres" (include "kavach.fullname" .) -}}
{{- end -}}

{{/*
Redis host — the in-chart Redis StatefulSet's service name.
*/}}
{{- define "kavach.redisHost" -}}
{{- printf "%s-redis" (include "kavach.fullname" .) -}}
{{- end -}}

{{/*
Shared volumes (uploads always a PVC; reports either a PVC or an
emptyDir depending on storage.reports.emptyDir) — included by every
Deployment that mounts /app/uploads and /app/reports (api, both worker
pools, beat).
*/}}
{{- define "kavach.sharedVolumes" -}}
- name: uploads
  persistentVolumeClaim:
    claimName: {{ include "kavach.fullname" . }}-uploads
- name: reports
  {{- if .Values.storage.reports.emptyDir }}
  emptyDir: {}
  {{- else }}
  persistentVolumeClaim:
    claimName: {{ include "kavach.fullname" . }}-reports
  {{- end }}
{{- end -}}

{{/*
Matching volumeMounts for kavach.sharedVolumes.
*/}}
{{- define "kavach.sharedVolumeMounts" -}}
- name: uploads
  mountPath: /app/uploads
- name: reports
  mountPath: /app/reports
{{- end -}}

{{/*
envFrom block shared by every KAVACH-image container (api, workers, beat).
*/}}
{{- define "kavach.envFrom" -}}
- configMapRef:
    name: {{ include "kavach.configMapName" . }}
- secretRef:
    name: {{ include "kavach.secretName" . }}
{{- end -}}
