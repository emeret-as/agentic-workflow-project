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

## 4. Results — 1:15

*Page "Results".*

The baseline is base Phi-3, same 56 held-out notes, same prompt and evaluation, adapters off. Exact match goes from 0% to 98.2%, valid schema from 0% to 100%, hallucinated-field rate from 27% to 1.8%.

Two points before you ask. The base model's 0% schema is partly unfair: we don't put the closed-list values in the prompt, so its free-form needs and actions fail the enum check. On the copied fields — company, contact, budget — the gap is 12 to 20 points.

And the 98% is not test-set overfitting: the split is held out and seed-fixed, eval loss is below train loss. The real limit is distribution — train and test share the same Gemini generator, so this is in-distribution, a best case. On real notes it would be lower, which is why we keep the hand-written out-of-distribution traps.

*Scroll to "Notes with a distractor".*

Four notes out of five have a distractor. The model misses one record, taking a seminar date as the deadline, on the one note whose accents were corrupted into tabs. Side note: 4-bit in the pipeline scores 55 of 56, float16 on the endpoint 56 of 56 — the quantization gap.

## 5. Monitoring — 1:15

*Page "Monitoring". The numbers on this page are read live from Langfuse — they already include the call I just ran in the demo.*

Every extraction the app does is logged as a trace: a span with the note and the record, and inside it a generation with the prompt, the parameters, the raw output, the model version and the latency.

*Point at the top row.*

Here, live: trace count, endpoint latency p50 and p95, and the judge breakdown — how many records faithful, minor, unfaithful.

*Point at the scores table.*

And the scores we attach to each trace. The first three run in our code on every call: valid JSON, valid schema, and `names_grounded` — company and contact actually in the note, a cheap hallucination proxy. The fourth is the one that matters in production, where we have no reference: the **LLM-as-a-judge**. Gemini rates how faithful the record is, 1 / 0.5 / 0 with a reason, few-shot so it doesn't read a seminar date as a deadline. It catches what the checks can't — the recipe, valid schema but fully made up, and the English note where it converted GBP to EUR on its own. Both score 0.

*Click "Open the Langfuse dashboard".*

Same scores plotted over time with the latency — that's our drift signal. One bias to flag: generator and judge are both Gemini, so the judge's few-shot examples are hand-written.

## Wrap-up — 0:30

To sum up: a small model, fine-tuned on synthetic data, fills in a CRM record reliably. It runs in our own cloud, and it is monitored on every call. The salesperson always has the last word. Thank you, we are happy to take questions.
