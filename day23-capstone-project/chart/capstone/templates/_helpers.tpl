{{- define "capstone.labels" -}}
app.kubernetes.io/part-of: capstone
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
