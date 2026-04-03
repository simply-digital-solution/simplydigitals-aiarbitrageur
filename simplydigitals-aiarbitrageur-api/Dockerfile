FROM public.ecr.aws/lambda/python:3.11 AS builder

RUN yum install -y gcc gcc-c++ libpq-devel python3-devel && yum clean all

COPY pyproject.toml .
RUN pip install --prefer-binary --no-cache-dir --target /packages ".[dev]" \
    && pip install --prefer-binary --no-cache-dir --target /packages .

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM public.ecr.aws/lambda/python:3.11

COPY --from=builder /packages ${LAMBDA_TASK_ROOT}
COPY app/ ${LAMBDA_TASK_ROOT}/app/
COPY alembic.ini ${LAMBDA_TASK_ROOT}/
COPY migrations/ ${LAMBDA_TASK_ROOT}/migrations/

CMD ["app.main.handler"]
