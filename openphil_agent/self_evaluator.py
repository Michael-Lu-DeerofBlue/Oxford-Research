"""
Self-evaluator that uses multimodal LLM to evaluate generated figures.
"""

import base64
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

from .generation import query


class SelfEvaluator:
    """
    Evaluates generated figures using multimodal LLM (GPT-4o vision).
    Uses a strict two-pass approach: criteria scoring + devil's advocate.
    """

    def __init__(
        self,
        model: str = "openai/gpt-4o",
        threshold: float = 0.9,
        require_consensus: bool = True,
    ):
        self.model = model
        self.threshold = threshold
        self.require_consensus = require_consensus

    def evaluate_figure(
        self,
        figure_path: Path,
        prompt: str,
        paper: str,
    ) -> Tuple[bool, float, str, Dict]:
        """
        Evaluate a generated figure against the task prompt and paper.
        
        Returns:
            (should_submit, score, reasoning, details)
        """
        if not figure_path.exists():
            return False, 0.0, "Figure file does not exist", {}

        with open(figure_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        criteria_result = self._evaluate_criteria(image_data, prompt, paper)
        
        devils_advocate_result = self._devils_advocate(image_data, prompt, paper)
        
        if self.require_consensus:
            criteria_result_2 = self._evaluate_criteria(image_data, prompt, paper)
            avg_score = (criteria_result["overall_score"] + criteria_result_2["overall_score"]) / 2
            consensus = abs(criteria_result["overall_score"] - criteria_result_2["overall_score"]) < 0.2
        else:
            avg_score = criteria_result["overall_score"]
            consensus = True

        has_blocking_issues = len(devils_advocate_result["blocking_issues"]) > 0
        meets_threshold = avg_score >= self.threshold
        should_submit = meets_threshold and not has_blocking_issues and consensus

        reasoning = self._build_reasoning(
            criteria_result,
            devils_advocate_result,
            avg_score,
            consensus,
            meets_threshold,
            has_blocking_issues,
        )

        details = {
            "criteria_evaluation": criteria_result,
            "devils_advocate": devils_advocate_result,
            "average_score": avg_score,
            "consensus": consensus,
            "meets_threshold": meets_threshold,
            "has_blocking_issues": has_blocking_issues,
        }

        return should_submit, avg_score, reasoning, details

    def _evaluate_criteria(
        self, image_data: str, prompt: str, paper: str
    ) -> Dict:
        """
        First pass: Extract criteria from prompt/paper and score each.
        """
        system_message = """You are a strict scientific figure evaluator. Your task is to:
1. Extract the key requirements from the task prompt and paper context
2. Evaluate the provided figure against each requirement
3. Provide an overall assessment

Be VERY STRICT. Only give high scores if the figure clearly meets all requirements.
A scientific figure should have:
- Clear, labeled axes with units
- Visible data/curves/plots
- Appropriate title or caption context
- Legend if multiple series
- Professional appearance
- Correct data representation matching the paper's description
"""

        user_message = f"""Task Prompt: {prompt}

Paper Context (excerpt): {paper[:2000]}

Please evaluate the figure shown in the image. Respond in JSON format with:
{{
    "requirements": [list of key requirements extracted from prompt/paper],
    "scores": {{requirement: score_0_to_1, ...}},
    "overall_score": float between 0 and 1,
    "description": "detailed description of what you see in the figure",
    "strengths": [list of strengths],
    "weaknesses": [list of weaknesses],
    "missing_elements": [list of missing critical elements]
}}

Be strict. Only give overall_score >= 0.9 if the figure is publication-quality and meets ALL requirements.
"""

        try:
            import os
            import openai
            
            client = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ["OPENROUTER_API_KEY"]
            )
            
            messages = [
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_message},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            }
                        }
                    ]
                }
            ]
            
            completion = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=2000,
            )
            
            response = completion.choices[0].message.content
            
            try:
                result = json.loads(response)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = {
                        "requirements": ["Unable to parse requirements"],
                        "scores": {},
                        "overall_score": 0.5,
                        "description": response,
                        "strengths": [],
                        "weaknesses": ["Unable to parse evaluation"],
                        "missing_elements": [],
                    }
            
            return result
        except Exception as e:
            return {
                "requirements": [],
                "scores": {},
                "overall_score": 0.0,
                "description": f"Error during evaluation: {str(e)}",
                "strengths": [],
                "weaknesses": [str(e)],
                "missing_elements": [],
            }

    def _devils_advocate(
        self, image_data: str, prompt: str, paper: str
    ) -> Dict:
        """
        Second pass: Devil's advocate - look for reasons to reject.
        """
        system_message = """You are a critical reviewer playing devil's advocate. Your job is to find ANY reasons why this figure should be REJECTED.

Look for:
- Missing or unlabeled axes
- Missing units
- Unclear or missing data
- Poor quality or unprofessional appearance
- Mismatch with the task requirements
- Any element that would make this unsuitable for publication

Be EXTREMELY critical. If you find ANY blocking issue, list it.
"""

        user_message = f"""Task Prompt: {prompt}

Paper Context (excerpt): {paper[:2000]}

Examine the figure critically. Respond in JSON format with:
{{
    "blocking_issues": [list of serious problems that should prevent submission],
    "minor_issues": [list of minor problems],
    "verdict": "REJECT" or "ACCEPT",
    "reasoning": "explanation of your verdict"
}}

Remember: Be STRICT. When in doubt, REJECT.
"""

        try:
            import os
            import openai
            
            client = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ["OPENROUTER_API_KEY"]
            )
            
            messages = [
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_message},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            }
                        }
                    ]
                }
            ]
            
            completion = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=2000,
            )
            
            response = completion.choices[0].message.content
            
            try:
                result = json.loads(response)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = {
                        "blocking_issues": ["Unable to parse evaluation"],
                        "minor_issues": [],
                        "verdict": "REJECT",
                        "reasoning": response,
                    }
            
            return result
        except Exception as e:
            return {
                "blocking_issues": [f"Evaluation error: {str(e)}"],
                "minor_issues": [],
                "verdict": "REJECT",
                "reasoning": str(e),
            }

    def _build_reasoning(
        self,
        criteria_result: Dict,
        devils_advocate_result: Dict,
        avg_score: float,
        consensus: bool,
        meets_threshold: bool,
        has_blocking_issues: bool,
    ) -> str:
        """Build human-readable reasoning for the evaluation decision."""
        parts = []
        
        parts.append(f"Average Score: {avg_score:.2f} (threshold: {self.threshold})")
        
        if not consensus:
            parts.append("⚠️ Multiple evaluations did not reach consensus")
        
        if criteria_result.get("description"):
            parts.append(f"\nFigure Description: {criteria_result['description']}")
        
        if criteria_result.get("strengths"):
            parts.append(f"\nStrengths: {', '.join(criteria_result['strengths'])}")
        
        if criteria_result.get("weaknesses"):
            parts.append(f"\nWeaknesses: {', '.join(criteria_result['weaknesses'])}")
        
        if criteria_result.get("missing_elements"):
            parts.append(f"\nMissing Elements: {', '.join(criteria_result['missing_elements'])}")
        
        if has_blocking_issues:
            parts.append(f"\n🚫 Blocking Issues: {', '.join(devils_advocate_result['blocking_issues'])}")
        
        if devils_advocate_result.get("minor_issues"):
            parts.append(f"\nMinor Issues: {', '.join(devils_advocate_result['minor_issues'])}")
        
        if meets_threshold and not has_blocking_issues and consensus:
            parts.append("\n✅ DECISION: SUBMIT - Figure meets all criteria")
        else:
            reasons = []
            if not meets_threshold:
                reasons.append(f"score {avg_score:.2f} below threshold {self.threshold}")
            if has_blocking_issues:
                reasons.append("has blocking issues")
            if not consensus:
                reasons.append("no consensus between evaluations")
            parts.append(f"\n❌ DECISION: DO NOT SUBMIT - {', '.join(reasons)}")
        
        return "\n".join(parts)

    def get_feedback_for_improvement(self, evaluation_details: Dict) -> str:
        """
        Extract actionable feedback from evaluation details for the agent to improve.
        """
        feedback_parts = []
        
        criteria = evaluation_details.get("criteria_evaluation", {})
        devils_advocate = evaluation_details.get("devils_advocate", {})
        
        if criteria.get("missing_elements"):
            feedback_parts.append(f"Missing elements: {', '.join(criteria['missing_elements'])}")
        
        if criteria.get("weaknesses"):
            feedback_parts.append(f"Weaknesses to address: {', '.join(criteria['weaknesses'])}")
        
        if devils_advocate.get("blocking_issues"):
            feedback_parts.append(f"Critical issues: {', '.join(devils_advocate['blocking_issues'])}")
        
        if devils_advocate.get("minor_issues"):
            feedback_parts.append(f"Minor improvements: {', '.join(devils_advocate['minor_issues'])}")
        
        if not feedback_parts:
            return "Figure is good but could be improved further for higher confidence."
        
        return " | ".join(feedback_parts)
