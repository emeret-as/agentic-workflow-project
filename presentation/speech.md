# Presentation script — Meeting notes → CRM record (10 minutes)

One section per page of the Streamlit app, in order. Parts 4 (Results) and 5 (Monitoring) are the
detailed versions and carry more than you need: say everything to go deep (~13 minutes total), or
trim to the key figures to stay near 10. *Italic lines* are actions, not words to say.

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

## 4. Results — 2:30

*Page "Results".*

To measure what fine-tuning actually brings, we always compare against a **baseline**: base Phi-3,
the model exactly as Microsoft publishes it, with no training. We ran a second pipeline that loads
base Phi-3 without our LoRA adapters, and runs it on the **same 56 test notes**, with the **same
prompt** and the **same evaluation component**. So the only thing that changes between the two
columns is the fine-tuning itself.

Here are the five metrics.
- **Valid JSON**: the answer is a readable JSON object. 88% for the base model, 100% fine-tuned.
- **Valid schema**: the seven keys in order, the right types — budget as an integer, deadline as a
  YYYY-MM-DD date — and the need and action taken from the closed lists. 0% for the base model,
  100% fine-tuned.
- **Exact match**: all seven fields equal to the reference record. 0% for the base model, 98%
  fine-tuned.
- **Field accuracy**: the share of correct fields on average. 53% to 99.7%.
- **Hallucinated field**: a record where the model fills a field the note never mentioned. From
  27% of records down to under 2%.

Now, we want to be honest about this, because 100% everywhere looks suspicious. Two things to say.

First, the base model's 0% on the schema is partly unfair. The prompt does **not** list the allowed
values, so base Phi-3 cannot guess that the need must be written exactly `crm_migration`; it writes
"CRM migration" in plain words, which fails the closed-list check. On the fields that are simply
**copied from the notes** — company, contact, budget — the gap is smaller, 12 to 20 points. The
base model's real weaknesses are the deadline, around a third correct, and invented values.

Second, is the fine-tuned model overfitting? Strictly, no. The 56 test notes are **held out**: the
model never sees them during training. And the overfitting signal would be a low train loss with a
high validation loss, but here it is the opposite — train loss 0.94, validation loss 0.76. We also
chose **three epochs** instead of ten precisely to avoid the overfitting we had seen earlier. That
said, the 100% is optimistic, and here is why: the test notes come from the **same synthetic
generator** as the training notes — same Gemini, same templates, same closed lists, same kinds of
distractors. So the model has learned the distribution very well, but on **real salespeople's
notes** the score would almost certainly be lower. That is exactly why we also tested hand-written
trap notes, which you saw in the demo.

*Scroll to "Notes with a distractor".*

The distractors were the hard part: four notes out of five contain one. The fine-tuned model
handles all of them except a single note, where it took a seminar date as the deadline — and that
note is actually a corrupted one, with its accents replaced by tabs. On the endpoint, where the
model runs in **float16** instead of 4 bits — so a bit more precise than in the pipeline — the same
56 notes give 56 exact records.

*Scroll to the training facts at the bottom.*

A word on the training itself. We use **LoRA**: instead of retraining the 3.8 billion parameters of
Phi-3, we only train small added matrices, 12.6 million parameters — that is what makes it cheap and
fast on a single T4. Three epochs means the model sees each training note three times.

## 5. Monitoring — 2:00

*Page "Monitoring". The figures are read live from Langfuse, including the calls of this demo.*

Results tell us how the model did **offline**, on a fixed test set where we know the answer. But in
production we have no reference answer, so we need **online** monitoring, and that is **Langfuse**.
We self-host it with Docker, which matters here: the notes talk about real clients, and they never
leave our machine.

Every record filled in creates a **trace**. It holds an outer **span** — the raw note as input, the
record as output — and inside it a **generation**, which keeps the exact prompt and parameters sent
to the model, the raw answer, the model version, and the **latency**. So for any record we can open
its trace and see exactly what the model received and returned.

On each trace we attach several **scores**:
- valid JSON and valid schema, the format checks;
- names grounded: whether the company and contact actually appear in the notes — a cheap way to
  catch invented names with no reference answer;
- and the score from our **LLM-as-a-judge**.

The judge is the key piece for production. Since we have no ground truth, we ask another model,
**Gemini**, to read the note and the record and rate how faithful the record is: 1, 0.5 or 0, with
a one-sentence reason. Its prompt has two hand-written examples, so it knows, for instance, that a
seminar date is not a deadline.

*Point at the judge figures.*

And it works: the judge gives 0 to the cooking recipe, where the format is perfect but everything is
invented, and 0 to an English note where the model converted pounds to euros on its own. These are
exactly the failures the format checks cannot see.

*Click "Open the Langfuse dashboard".*

In the dashboard, the same scores are plotted **over time**, together with the endpoint latency,
p50 and p95. This is how we would detect **drift**: if real notes start to look different from our
training data — a new style, another language — these curves drop, and that is the signal to
retrain, using the records the salespeople validated as fresh labelled data.

One honest limitation on the judge: our training data and our judge both come from Gemini, so they
may share the same blind spots. That is why the judge's examples are written by hand, not generated.

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
