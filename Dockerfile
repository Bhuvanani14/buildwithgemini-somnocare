# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3.12-slim

WORKDIR /code

COPY ./pyproject.toml ./README.md ./

RUN pip install --no-cache-dir \
    fastapi>=0.115.0 \
    uvicorn[standard]>=0.34.0 \
    google-genai>=1.9.0 \
    google-adk>=1.16.0 \
    google-cloud-firestore>=2.19.0 \
    google-cloud-logging>=3.12.0 \
    reportlab>=4.2.0 \
    PyPDF2>=3.0.0 \
    python-multipart>=0.0.9 \
    python-dotenv>=1.0.0 \
    httpx>=0.27.0

COPY ./app ./app
COPY ./frontend ./frontend
COPY ./data ./data

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "frontend/main.py"]
