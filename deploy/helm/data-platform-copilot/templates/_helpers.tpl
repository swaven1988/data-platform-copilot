{{- define "data-platform-copilot.name" -}}
data-platform-copilot
{{- end -}}

{{- define "data-platform-copilot.fullname" -}}
{{ include "data-platform-copilot.name" . }}
{{- end -}}
