# Presentation script — Meeting notes → CRM record (10 minutes)

One section per page of the Streamlit app, in order. Times are targets: about 1,100 spoken words
(8.5 minutes at a calm pace) plus the waiting time of the live demo, so 10 minutes in total.
*Italic lines* are actions, not words to say.

**Before you start**
- *Deploy the endpoint ~30 minutes before (it takes 15–30 min).*
- *Put `GCP_ENDPOINT_ID` in `.env`, then start the app.*
- *Check Langfuse is running at http://localhost:3000.*
- *On the Demo page, click "Wake up the endpoint" once.*
- *If the endpoint fails during the talk: switch the sidebar to "Recorded replay". Same examples, real answers recorded from the model.*

---

## 1. Brief — 2:00

*Page "Brief": the dictated note on the left, the CRM record on the right.*

After every client meeting, a B2B salesperson has to copy their notes into the CRM. Company,
contact, what the client needs, the budget, the next step, the deadline. It is slow, so it gets
done badly or not at all: incomplete records, forgotten follow-ups, wrong sales forecasts.

Our product takes the raw notes, exactly as the salesperson typed or dictated them, and fills in
the CRM record. On the left is a real dictated note, in French, with hesitations and a trap: the
contact will be on holiday on the 12th of May. On the right is what our model returned. Each
highlight shows where a field comes from in the notes. The holiday date was ignored, and the
deadline is the 14th of July. The record is stamped "AI draft": nothing is saved until the
salesperson validates it.

*Scroll to the table.*

The record has seven fields. Two of them, the need and the next action, are closed lists, as in a
real CRM: eight possible needs, six possible actions. A value outside the list could not be saved,
so our guardrail rejects it.

Why a small fine-tuned model rather than a big general API? Three reasons.
- **Confidentiality.** These notes talk about real clients. The model runs in our own Google Cloud
  project, and nothing goes to an external API.
- **Cost.** Phi-3-mini fits on one T4 GPU, and LoRA trains only 12.6 million parameters.
- **Format.** Without training, Phi-3 knows neither our closed lists nor our format. We measure
  exactly that.

Success means three things: valid JSON every time, the right value in each field, and no invented
values.

## 2. Demo — 3:00

*Page "Demo", source "Live model". Click the "Dictated" example, then "Fill in the record".*

This is the real model, served on a Vertex AI endpoint. It takes about five to ten seconds on a T4.

*When the record appears:*

We get the record and the highlights. The badges at the bottom are the automatic checks: valid
JSON, valid schema, the latency. The last badge is our LLM judge: Gemini re-reads the notes and the
record, and gives a fidelity score with a one-line reason. Here it is one out of one.

Now a trap. *Click "Recipe", then "Fill in the record".*

This is not a meeting note at all, it is a cooking recipe. The model still produces a perfectly
formatted record, with a clinic and a contact that do not exist. This is the most dangerous
failure, because the format is perfect. Look at the record: every name is flagged "not in the notes ·
check it", and the judge gives zero. The salesperson sees it immediately.

Second trap. *Click "Off-list", then "Fill in the record".*

The client wants a new website, which is not in our list of needs. The model invents a category,
"website_redesign". The guardrail rejects the record: nothing is displayed as a valid record, and
nothing is saved.

Last step, the human in the loop. *Back on a valid record, scroll to "Validation by the
salesperson", change one field, click "Validate the record".*

The stamp turns to "Validated". The corrected record goes to Langfuse as the correct answer, with
the number of fields the salesperson had to change. That is how the product would collect real
labelled data in production.

## 3. Pipeline — 1:15

*Page "Pipeline".*

This is the course workflow, end to end, with our own data, prompt and metrics.

**Prepare.** No public dataset fitted, so we built one. We first draw a record, then Gemini writes the meeting
note: six styles, three lengths, and in four notes out of five a distractor (another date, a
competitor's budget, a colleague). A second, independent extraction must find the same record,
otherwise the note is dropped. We kept 558 notes.

**Train.** This is a Kubeflow pipeline on Vertex AI, with four components:
- transformation into the Phi-3 chat format;
- LoRA fine-tuning on Phi-3 loaded in 4 bits, 3 epochs, 79 minutes on a T4;
- inference on 56 test notes;
- evaluation.

**Serve and monitor.** The model is registered in the Model Registry with a custom handler, then
deployed on an endpoint. The endpoint is called by this app, and every call is traced in a
self-hosted Langfuse.

## 4. Results — 1:30

*Page "Results".*

To know what fine-tuning actually brings, we ran a second pipeline with base Phi-3 on the same 56
notes, the same prompt and the same evaluation component.
- Valid JSON goes from 88% to 100%.
- Valid schema goes from 0% to 100%.
- Exact records, all seven fields right, go from 0% to 98%.
- Records with an invented field drop from 27% to under 2%.

We want to be honest about the gap. The prompt does not list the closed-list values, so base
Phi-3 simply cannot guess "crm_migration". On the fields copied from the notes the gap is 12 to
20 points. The real weakness of the base model is the deadline and invented values.

*Scroll to "Notes with a distractor".*

The distractors were the hard part. The fine-tuned model handles all of them except one note: it
took a seminar date for the deadline. On the endpoint, where the model runs in float16 instead of
4 bits, the same 56 notes give 56 exact records.

## 5. Monitoring — 1:15

*Page "Monitoring". The figures are read live from Langfuse, including the calls of this demo.*

Every record leaves a trace in Langfuse: the notes, the prompt and parameters sent to the model,
the raw answer, the model version and the latency. On each trace we score:
- valid JSON and valid schema;
- whether the company and contact names really appear in the notes;
- the LLM judge's fidelity score.

*Point at the judge figures.*

The judge flags the traps, the recipe and an English note where the model converted pounds to
euros on its own. *Click "Open the Langfuse dashboard".* The same scores over time, with the
endpoint latency, are in the Langfuse dashboard. A drop in these curves is how we would detect
drift.

## 6. Problems — 1:00

*Page "Problems".*

The main problems we hit, and what we changed.
- **Data.** The free Gemini key allowed 20 requests a day, so we generated the data on Vertex AI.
  We also found 13 notes where accents had been replaced by tabs. That is exactly the note the
  pipeline got wrong, and the filter must be fixed before the next training run.
- **Serving.** The endpoint deployment was refused because the CPU quota is shared with the other
  teams, so we moved to a smaller machine. An endpoint is billed as long as it exists, so we
  delete it after every use.
- **Monitoring.** Langfuse's own LLM connection failed with a free Gemini key, so our judge calls
  Gemini through Vertex AI and writes its score into Langfuse.

To sum up: a small model, fine-tuned on synthetic data, fills in a CRM record reliably. It runs
in our own cloud, and it is monitored on every call. The salesperson always has the last word.
Thank you, we are happy to take questions.
