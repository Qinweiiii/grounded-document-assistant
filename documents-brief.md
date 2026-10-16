# Document assistant

Build a grounded document assistant and decide how it should balance useful answers, conflicting source passages and user trust.

Hardware and model access: Model access may be needed
If you use a real model, provide access through a suitable inference machine or model API. The supplied baseline and small document checks do not require a GPU.

Your role: Engineer responsible for an internal document assistant.

Decision scenario: Colleagues need answers quickly, but policy documents can be incomplete or conflicting. A helpful answer may save time while an unsupported answer can cause someone to act on the wrong policy.

Affected stakeholders: People asking questions, document owners and colleagues affected by the resulting decisions.

Scope and constraints: Use the supplied document baseline and add small evaluation cases. There is no requirement to integrate real company systems or use sensitive records.

Decision to defend: When would you answer, qualify the answer or abstain, and whose needs and risks justify your choice?

This is an assessment scenario, not a claim about measured results. State any additional assumptions; you may choose a different reasonable option. Use your code and run results to support your own judgment, and explain what remains unknown.

Submitted work
Provide a bounded, reproducible implementation or experiment, run instructions, results and limitations that satisfy the requirements below. AI assistance is allowed when disclosed. A larger codebase or system does not by itself improve the quality of the submitted results.

Requirements:
- Answer from supplied documents with passage citations.
- Handle missing and conflicting source passages.
- Evaluate normal, unsupported and adversarial questions.

Personal judgment
Use this scenario and decisions from your actual work to explain your priorities, stakeholder tradeoffs, uncertainty and reflection in the four decision-journal questions. Several conclusions can be defensible; there is no required preferred opinion. Be ready to discuss your reasoning during an on-site interview.
- Your priorities and values: Choose how this assistant should balance helpful answers with admitting uncertainty. Explain which user need you prioritize.
- Your tradeoff and stakeholder judgment: When sources conflict, compare abstaining, presenting both views and selecting one source. Defend your choice for a specific user.
- Your judgment under uncertainty: A user needs an urgent answer but support is incomplete. Explain the risk you accept, your limits and what would change your decision.
- Your ownership and reflection: Describe a citation, refusal or answer you personally changed or retained after review. Explain your reasoning and what you learned.

Run the supplied baseline with Python 3: python documents-baseline.py
Extend it within the stated task scope. Include source files, exact run commands, output tables or plots, failed cases and known limitations.

We recommend selecting 1–3 tasks; choosing more is allowed. Save answers as you work and return before the displayed deadline. The 48-hour (two-day) window starts at the invitation effective time and is a return/submission deadline, not expected working time.

AI may assist implementation. Use your own logic in the decision journal and be ready to discuss it without AI assistance during an on-site interview.
