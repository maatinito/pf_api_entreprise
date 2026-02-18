FROM golang:1.24-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go mod tidy
RUN CGO_ENABLED=0 GOOS=linux go build -o /pf-entreprise .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
COPY --from=builder /pf-entreprise /pf-entreprise
EXPOSE 3000
CMD ["/pf-entreprise"]
