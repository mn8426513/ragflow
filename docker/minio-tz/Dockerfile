FROM mysql:8.0.40 AS tzdata

FROM pgsty/silo:RELEASE.2026-08-06T00-00-00Z

COPY --from=tzdata /usr/share/zoneinfo /usr/share/zoneinfo

ENV TZ=Asia/Shanghai