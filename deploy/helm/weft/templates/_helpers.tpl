{{- define "weft.name" -}}weft{{- end -}}
{{- define "weft.fullname" -}}{{ .Release.Name }}-{{ include "weft.name" . }}{{- end -}}
{{- define "weft.labels" -}}
app.kubernetes.io/name: {{ include "weft.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}
{{- define "weft.selector" -}}
app.kubernetes.io/name: {{ include "weft.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
{{- define "weft.image" -}}
{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}
{{- end -}}
{{- define "weft.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{ .Values.secrets.existingSecret }}
{{- else -}}
{{ include "weft.fullname" . }}-secrets
{{- end -}}
{{- end -}}
{{- define "weft.filesClaim" -}}
{{- if .Values.persistence.existingClaim -}}
{{ .Values.persistence.existingClaim }}
{{- else -}}
{{ include "weft.fullname" . }}-files
{{- end -}}
{{- end -}}
{{- define "weft.backupClaim" -}}
{{- if .Values.backup.existingClaim -}}
{{ .Values.backup.existingClaim }}
{{- else -}}
{{ include "weft.fullname" . }}-backups
{{- end -}}
{{- end -}}
{{- define "weft.backupImage" -}}
{{ .Values.backup.image }}
{{- end -}}
{{- define "weft.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{ .Values.serviceAccount.name | default (include "weft.fullname" .) }}
{{- else -}}
{{ .Values.serviceAccount.name | default "default" }}
{{- end -}}
{{- end -}}
