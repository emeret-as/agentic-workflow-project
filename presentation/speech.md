# Presentation script — Meeting notes → CRM record (10 minutes)

One section per page of the Streamlit app, in order. Parts 4 (Results) and 5 (Monitoring) are the detailed versions and carry more than you need: say everything to go deep (~13 minutes total), or trim to the key figures to stay near 10. *Italic lines* are actions, not words to say.

**Before you start**
- *Deploy the endpoint ~30 minutes before (it takes 15–30 min).*
- *Put `GCP_ENDPOINT_ID` in `.env`, then start the app.*
- *Check Langfuse is running at http://localhost:3000.*
- *On the Demo page, click "Wake up the endpoint" once.*
- *If the endpoint fails during the talk: switch the sidebar to "Recorded replay". Same examples, real answers recorded from the model.*

---

## 1. Brief — 2:00

*Page "Brief": the dictated note on the left, the CRM record on the right.*

After every client meeting, a B2B salesperson has to copy their notes into the CRM. Company, contact, what the client needs, the budget, the next step, the deadline. It is slow, so it gets done badly or not at all: incomplete records, forgotten follow-ups, wrong sales forecasts.

Our product takes the raw notes, exactly as the salesperson typed or dictated them, and fills in the CRM record. On the left is a real dictated note, in French, with hesitations and a trap: the contact will be on holiday on the 12th of May. On the right is what our model returned. Each highlight shows where a field comes from in the notes. The holiday date was ignored, and the deadline is the 14th of July. The record is stamped "AI draft": nothing is saved until the salesperson validates it.

*Scroll to the table.*

The record has seven fields. Two of them, the need and the next action, are closed lists, as in a real CRM: eight possible needs, six possible actions. A value outside the list could not be saved, so our guardrail rejects it.

Why a small fine-tuned model rather than a big general API? Three reasons.
- **Confidentiality.** These notes talk about real clients. The model runs in our own Google Cloud project, and nothing goes to an external API.
- **Cost.** Phi-3-mini fits on one T4 GPU, and LoRA trains only 12.6 million parameters.
- **Format.** Without training, Phi-3 knows neither our closed lists nor our format. We measure exactly that.

Success means three things: valid JSON every time, the right value in each field, and no invented values.

## 2. Demo — 3:00

*Page "Demo", source "Live model". Click the "Dictated" example, then "Fill in the record".*

This is the real model, served on a Vertex AI endpoint. It takes about five to ten seconds on a T4.

*When the record appears:*

We get the record and the highlights. The badges at the bottom are the automatic checks: valid JSON, valid schema, the latency. The last badge is our LLM judge: Gemini re-reads the notes and the record, and gives a fidelity score with a one-line reason. Here it is one out of one.

Now a trap. *Click "Recipe", then "Fill in the record".*

This is not a meeting note at all, it is a cooking recipe. The model still produces a perfectly formatted record, with a clinic and a contact that do not exist. This is the most dangerous failure, because the format is perfect. Look at the record: every name is flagged "not in the notes · check it", and the judge gives zero. The salesperson sees it immediately.

Second trap. *Click "Off-list", then "Fill in the record".*

The client wants a new website, which is not in our list of needs. The model invents a category, "website_redesign". The guardrail rejects the record: nothing is displayed as a valid record, and nothing is saved.

Last step, the human in the loop. *Back on a valid record, scroll to "Validation by the salesperson", change one field, click "Validate the record".*

The stamp turns to "Validated". The corrected record goes to Langfuse as the correct answer, with the number of fields the salesperson had to change. That is how the product would collect real labelled data in production.

## 3. Pipeline — 1:15

*Page "Pipeline".*

This is the course workflow, end to end, with our own data, prompt and metrics.

**Prepare.** No public dataset fitted, so we built one. We first draw a record, then Gemini writes the meeting note: six styles, three lengths, and in four notes out of five a distractor (another date, a competitor's budget, a colleague). A second, independent extraction must find the same record, otherwise the note is dropped. We kept 558 notes.

**Train.** This is a Kubeflow pipeline on Vertex AI, with four components:
- transformation into the Phi-3 chat format;
- LoRA fine-tuning on Phi-3 loaded in 4 bits, 3 epochs, 79 minutes on a T4;
- inference on 56 test notes;
- evaluation.

**Serve and monitor.** The model is registered in the Model Registry with a custom handler, then deployed on an endpoint. The endpoint is called by this app, and every call is traced in a self-hosted Langfuse.

## 4. Results — 2:00

*Page "Results".*

The baseline is base Phi-3, run through a second pipeline on the same 56 held-out notes, same prompt, same evaluation, with the LoRA adapters off. So the difference between the two columns is only the fine-tuning.

*Point at the table.*

Exact match goes from 0% to 98.2%, valid schema from 0% to 100%, and the hallucinated-field rate from 27% down to 1.8%. Field accuracy from 53% to 99.7%.

Two points before you ask. First, the base model's 0% on schema is partly unfair: we don't put the closed-list values in the prompt, so it writes free-form needs and actions that fail the enum check. On the fields it just copies from the note — company, contact, budget — the gap is 12 to 20 points, and that is the honest measure of what fine-tuning adds here.

Second, the 98% exact match: this is not overfitting on the test set. The split is held out and seed-fixed, and eval loss is below train loss, 0.76 against 0.94, on 3 epochs. The real limit is the distribution: train and test come from the same Gemini generator, same templates, same kinds of distractors. So this is in-distribution performance — a best case. On real sales notes it would be lower, which is why we keep the hand-written out-of-distribution traps as a separate check.

*Scroll to "Notes with a distractor".*

Four notes out of five have a distractor, and the breakdown per distractor is the interesting part. The fine-tuned model misses one record only: it takes a seminar date as the deadline, on the one note whose accents were corrupted into tabs. One more thing: the pipeline runs in 4-bit and scores 55 of 56, the float16 endpoint scores 56 of 56 on the same notes — that is the quantization gap.

## 5. Monitoring — 1:45

*Page "Monitoring". Figures are read live from Langfuse, including this demo's calls.*

Offline we score against references. Online we have none, so the scores have to be reference-free. Langfuse is self-hosted — the notes are client data and stay on our machine.

Each extraction is one trace: a span at the record level, and inside it a generation for the endpoint call, with the prompt, the parameters, the raw output, the model version and the latency. On each one we push reference-free scores: the two schema checks, and `names_grounded`, which checks that the company and contact appear in the note — a cheap hallucination proxy.

The real reference-free signal is the **LLM-as-a-judge**: Gemini rates how faithful the record is to the note, 1 / 0.5 / 0 with a reason, few-shot with two hand-written examples so a seminar date is not read as a deadline.

*Point at the judge figures.*

It catches what the deterministic checks can't: the recipe, where the schema is valid but everything is made up, and an English note where the model quietly converted GBP to EUR. Both score 0.

*Click "Open the Langfuse dashboard".*

Scores over time, with p50/p95 latency. This is the drift signal: if the input distribution shifts, it shows up as a drop here, and the validated records give us the labelled data to retrain on.

One bias to flag: the generator and the judge are both Gemini, so they can share blind spots. That is why the judge's few-shot examples are hand-written, not generated.

## Wrap-up — 0:30

To sum up: a small model, fine-tuned on synthetic data, fills in a CRM record reliably. It runs in our own cloud, and it is monitored on every call. The salesperson always has the last word. Thank you, we are happy to take questions.
