{{- define "odf.name" -}}odf{{- end -}}
{{- define "odf.fullname" -}}{{ .Release.Name }}-{{ include "odf.name" . }}{{- end -}}
{{- define "odf.labels" -}}
app.kubernetes.io/name: {{ include "odf.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}
{{- define "odf.selector" -}}
app.kubernetes.io/name: {{ include "odf.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
{{- define "odf.image" -}}
{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}
{{- end -}}
{{- define "odf.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{ .Values.secrets.existingSecret }}
{{- else -}}
{{ include "odf.fullname" . }}-secrets
{{- end -}}
{{- end -}}
{{- define "odf.filesClaim" -}}
{{- if .Values.persistence.existingClaim -}}
{{ .Values.persistence.existingClaim }}
{{- else -}}
{{ include "odf.fullname" . }}-files
{{- end -}}
{{- end -}}
{{- define "odf.backupClaim" -}}
{{- if .Values.backup.existingClaim -}}
{{ .Values.backup.existingClaim }}
{{- else -}}
{{ include "odf.fullname" . }}-backups
{{- end -}}
{{- end -}}
{{- define "odf.backupImage" -}}
{{ .Values.backup.image }}
{{- end -}}
{{- define "odf.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{ .Values.serviceAccount.name | default (include "odf.fullname" .) }}
{{- else -}}
{{ .Values.serviceAccount.name | default "default" }}
{{- end -}}
{{- end -}}
