## What is traced
Each record filled in creates a `User Message` trace, holding the notes as input and the record as output. Inside it, a `Vertex AI endpoint` generation keeps:
- the request sent (prompt and generation parameters);
- the raw answer;
- the model, its version and the response time.

An endpoint failure is marked `ERROR`.

## The LLM judge
For every valid record, Gemini reads the notes and the record and gives a fidelity score (1, 0.5 or 0) with a one-sentence reason. Its prompt has two hand-written examples (few-shot), and the reason is stored as a comment on the score.

The course sets the judge up inside Langfuse, with an LLM connection. Our free Gemini key failed there, because the models were overloaded. So the judge calls Gemini through Vertex AI with our GCP project, then writes its score into Langfuse. The result in Langfuse is the same: a score on every trace, visible in the dashboard.

## What monitoring has already caught
On the hand-written trap notes:
- **The cooking recipe** got a "valid" record, entirely made up ("Clinique Valmont", "Sophie Bernard"). `names_grounded` and the judge both give 0.
- **The off-list need** (redoing a website) produced an invented category, `website_redesign`. The guardrail blocks the record.
- **The English note** passes the format checks, but its budget of £80k is converted to €72,000 without the note saying so. The judge gives 0.

**Limit:** the training notes and the judge both come from Gemini, so they may share the same blind spots.
