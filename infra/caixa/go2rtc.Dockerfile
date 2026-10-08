# O go2rtc da caixa (MIT; SDD 7.4, D-66): recebe cada câmera uma vez só e a repassa ao agente.
#   docker build -f infra/caixa/go2rtc.Dockerfile -t patio-go2rtc:local infra/caixa
#
# Montado aqui a partir do código, e não a imagem oficial: ela instala um FFmpeg do Alpine com
# partes GPL (x264 e x265), que a D-27 não deixa. Repassar o RTSP não precisa de FFmpeg.
# O código vem pelo proxy de módulos do Go, que confere o resumo de cada módulo no banco público
# de resumos (sum.golang.org): um módulo adulterado não monta.
FROM golang:1.25-alpine AS montagem
ARG GO2RTC=v1.9.14
# Como o próprio go2rtc monta o binário dele (build.yml): estático, sem os símbolos de depuração.
RUN CGO_ENABLED=0 GOBIN=/saida go install -trimpath -ldflags "-s -w" \
    "github.com/AlexxIT/go2rtc@${GO2RTC}"
# As licenças do go2rtc, dos módulos dele e do Go vão junto com o binário (MIT e BSD pedem).
RUN mkdir -p /saida/licencas && cp /usr/local/go/LICENSE /saida/licencas/go \
    && cd /go/pkg/mod && find . -path ./cache -prune -o -type f \
        \( -iname 'licen[cs]e*' -o -iname 'copying*' -o -name 'edl-v10' -o -name 'epl-v20' \) \
        -print | while read -r arquivo; do \
            cp "$arquivo" "/saida/licencas/$(echo "${arquivo#./}" | tr '/' '_')"; \
        done

# A imagem final só tem o binário e as licenças: sem sistema, sem pacotes, sem usuário root.
FROM scratch
COPY --from=montagem /saida/go2rtc /go2rtc
COPY --from=montagem /saida/licencas /licencas
USER 10002:10002
EXPOSE 1984 8554
ENTRYPOINT ["/go2rtc"]
# A configuração vai inteira aqui, sem arquivo: o go2rtc não tem onde gravar a senha de uma
# câmera. A API e o RTSP ficam na rede dos contêineres; o WebRTC e o SRTP, desligados.
CMD ["-c", "{api: {listen: ':1984'}, rtsp: {listen: ':8554'}, webrtc: {listen: ''}, srtp: {listen: ''}, log: {level: warn, format: text}}"]
