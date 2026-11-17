Does swapping A and B change an LLM judge’s verdict?

I ran 48 local judgments with Qwen2.5 7B and Qwen3 8B. Eight Python tasks each had one valid implementation and one implementation with a known defect. Each judge saw both A/B orders, plus eight comparisons where the contract required a tie.

Before inference, executable tests checked the valid implementations, the defects and valid alternatives. The judges saw the contract and code, without tests or gold labels.

Main results:
• Qwen2.5: 6/16 correct judgments; the same substantive decision in 7/8 pairs; a changed decision in 1/8.
• Qwen3: 10/16 correct judgments; the same decision in 4/8 pairs; a changed decision in 4/8.

“Same decision” includes TIE. Four of Qwen2.5’s seven consistent pairs were ties in both orders, even though exactly one implementation passed the contract tests.

Average accuracy by position was identical: Qwen2.5 scored 3/8 with the valid code first and 3/8 with it second; Qwen3 scored 5/8 in each position. Those equal totals hid the changes within individual pairs.

Tie controls scored 8/8 and 7/8 respectively. All 48 responses matched the JSON schema; none hit the output cap. Consistency, correctness and output validity measured different things here.

I used INVARIANT to coordinate evaluator implementation, eight fixed acceptance checks and implementation review. A separate auditor reconstructed all prompts, execution labels and paired metrics from the saved evidence.

This is a small synthetic diagnostic: eight simple tasks, one seed, fixed prompts and two older quantized local models with thinking disabled. It does not estimate population position bias, human preference agreement or frontier-model quality. Rationales were saved but not scored.

Code, protocol, raw responses and chart:
https://github.com/Xenox-developer/judge-order-lab

INVARIANT:
https://github.com/Xenox-developer/invariant

Primary source:
https://arxiv.org/abs/2306.05685
