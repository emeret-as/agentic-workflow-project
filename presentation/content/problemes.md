| Problem | What we changed |
|---|---|
| The practice use case (Yoda-speak translation) was not ours | Switched to meeting notes → CRM record, keeping the whole course pipeline and changing the data, prompt and metrics |
| No public dataset fits (the "text → JSON" sets we found are generic, and their records contain inventions) | Synthetic data: we draw the record first, then Gemini writes the note. A second extraction checks every note: 558 notes kept. |
| Free Gemini key limited to 20 requests a day | Data generated with Gemini on Vertex AI, in our GCP project, for a few cents |
| 32 generated notes contained invisible characters | `has_corrupted_text` filter before training |
| 13 notes have "é" replaced by tabs: the filter allows tabs, so they got through | Found while analysing errors. It is the only note the pipeline got wrong. The filter must be fixed before the next training run. |
| Overfitting in the Yoda practice: validation loss went up after 2 epochs | 3 epochs instead of 10 (Rouge-L from 0.831 to 0.861) |
| Output length: the record takes 58 to 92 tokens, and full examples up to 512 | `max_length` 640 for training, `max_new_tokens` 160 for serving |
| Endpoint deployment refused: CPU quota shared with the other teams | `n1-standard-4` instead of `n1-standard-8`, with a script that deploys and deletes the endpoint |
| An endpoint is billed as long as it exists, with no scale-to-zero | Deleted after every use, redeployed about 30 minutes before the demo |
| Langfuse v4 rejects the old read routes (`/traces`, `/scores`) | Reads through `/api/public/v2/observations` and `/api/public/v3/scores`. SDK kept at v3: v5 no longer has `start_as_current_generation`. |
| Port 5432 already taken by a local Postgres, Docker limited to 4 GB | Langfuse's Postgres exposed on 5433 (`docker-compose.override.yml`); Langfuse uses about 2.4 GB |
| Langfuse's LLM connection failed with our free Gemini key (models closed to new users, then overloaded) | The LLM judge calls Gemini through Vertex AI with our GCP project, and writes its score into Langfuse |
| Gap between the pipeline (55/56 exact records) and the endpoint (56/56) | The pipeline loads Phi-3 in 4 bits, the endpoint in float16: quantization costs one record |
