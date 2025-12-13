import json
import os
import re # 导入正则表达式模块
import subprocess
import sys
from typing import Any, Dict, Optional, List
from openai import OpenAI


class ReActAgent:
    """
    类式 ReAct Agent：Thought→Action→Observation。
    遵循标准文本协议 (Thought, Action, Action Input, Observation, Final Answer)。
    """

    # -------------------------- 实现React Agent的PROMPT ---------------------------
    # 可以仿照如下PROMPT来进行改写，以提升模型Agent能力为目标
    
    INSTRUCTION = (
        "Answer the following questions as best you can. You must run Python code to obtain the final answer.\n"
        "You have access to the following tool:\n"
        "- python: execute Python code in a secure sandbox.\n"
        "Use the following format (do NOT fabricate Observation; it is appended by the environment):\n\n"
        "Question: the input question you must answer (includes data path)\n"
        "Thought: you should always think about what to do\n\n"
        "Action: the action to take, should be one of [python]\n\n"
        "Action Input:\n```python\n[the input Python code for the action]\n```\n"
        "Important: Only STDOUT printed via print(...) is captured; ensure you print your results. Do not use plot.show().\n"
        "Observation: the result of the action (provided by the environment; do NOT generate this yourself)\n\n"
        "This Thought/Action/Action Input/Observation cycle can repeat N times.\n"
        "Only output 'Final Answer' once you are certain based on the environment's Observation.\n"
        "Final Answer: the final answer to the original input question\n"
        "When you output Final Answer, output ONLY the @key[value] lines, no extra text.\n"
        "Express percentages as decimals.\n"
        "Working directory is the project root. Begin!\n"
        "/no_think\n"
    )

    # -----------------------------------------------------------------------------


    def __init__(
        self,
        base_url: str = os.environ.get("OPENAI_API_BASE", "https://ai.gitee.com/v1"),
        api_key: str = os.environ.get("OPENAI_API_KEY", "LJOUGSSDC5MOWLHT4Y6MAEDVTR0MTTELCWB40GP6"),
        model: str = os.environ.get("OPENAI_API_MODEL", "Qwen3-32B"),
    ):
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        self.model = model

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """调用 LLM 并设置 stop 序列以防止模型生成 Observation"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            # 设置 stop 序列以防止模型生成 Observation 或 Final Answer，保证流程控制
            stop=["Observation:"],
        )
        return response.choices[0].message.content.strip()

    def _react_once(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """调用 LLM 并解析输出为 Thought/Action 或 Final Answer"""
        out = self._call_llm(messages)
        print("model output:\n", out)

        parsed = self._parse_react_text(out)

        if parsed:
            parsed["raw"] = out
            return parsed

        # 无法解析则报错，不进行任何回退代码执行
        return {"action": "error", "message": f"无法解析 LLM 输出为 Thought/Action 或 Final Answer: {out}"}

    # ReAct Agent 类中替换 _parse_react_text 方法
    def _parse_react_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        从 ReAct 文本中解析 Thought, Action, Action Input, 或 Final Answer。
        增强容错性，支持 <think> 标签和裸代码块。
        """

        # 1. 尝试解析 Final Answer (优先级最高)
        m_fa = re.search(r"Final Answer:\s*([\s\S]*)", text, re.IGNORECASE)
        if m_fa:
            fa = m_fa.group(1)  
            fa = fa.strip()  
            fa = fa.replace("\\n", "\n")  
            fa = re.sub(r"[ \t]+\n", "\n", fa)  
            fa = re.sub(r"\n[ \t]+", "\n", fa)  
            lines = [ln.strip() for ln in fa.splitlines() if ln.strip()]  # 每行去空格，去空行
            fa = "\n".join(lines)  
            return {"action": "final", "final_answer": fa}  

        # 2. 尝试解析 Thought (支持 <think> 标签或标准 Thought: 标签)

        # 尝试匹配 <think>...</think>
        m_think_tag = re.search(r"<think>([\s\S]*?)</think>", text)
        if m_think_tag:
            thought = m_think_tag.group(1).strip()
        else:
            # 尝试匹配标准 Thought: 标签
            m_thought = re.search(r"Thought:\s*([\s\S]*?)(?=Action:|Action Input:|Final Answer:|$)", text)
            thought = m_thought.group(1).strip() if m_thought else "No formal Thought label found, checking for code action."

        # 3. 尝试解析 Action Input (支持带标签或裸代码块)

        # 优先匹配 Action Input: ```python ... ```
        m_code_labeled = re.search(r"Action Input:\s*```python\n([\s\S]*?)```", text)
        if m_code_labeled:
            code = m_code_labeled.group(1).strip()
        else:
            # 回退：匹配裸 ```python ... ``` 代码块 (模型最容易输出的形式)
            m_code_plain = re.search(r"```python\n([\s\S]*?)```", text)
            code = m_code_plain.group(1).strip() if m_code_plain else None

        # 4. 尝试解析 Action (可选，因为裸代码块即暗示 Action: python)
        m_action = re.search(r"Action:\s*([a-zA-Z_]+)", text)
        action = m_action.group(1).strip() if m_action else "python" # 默认假设

        # 5. 组合结果
        if code:
            # 如果找到了代码，就执行 python 动作，Thought 使用解析到的结果
            return {"thought": thought, "action": "python", "code": code}

        # 如果没有匹配到任何代码或最终答案
        return None

    def run_code(self, code: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        """在沙盒中执行 Python 代码"""
        # 确定执行工作目录：使用当前文件目录的上级目录作为项目根目录
        try:
            # 兼容 Notebook/Script 环境
            file_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(file_dir, ".."))
            base_dir = project_root if os.path.isdir(project_root) else file_dir
        except NameError:
            base_dir = os.getcwd() # __file__ 未定义，使用当前工作目录

        # 如果提供了 cwd，则覆盖
        base_dir = cwd or base_dir

        try:
            # 使用 sys.executable 确保在不同的 Python 环境中都能找到正确的解释器
            python_bin = sys.executable or "python3"
            proc = subprocess.run(
                [python_bin, "-c", code],
                cwd=base_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=40,
            )
            out = {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired as e:
            out = {
                "stdout": e.stdout or "",
                "stderr": (e.stderr or "") + "\nTimeoutExpired",
                "returncode": 124,
            }
        return out

    def _format_observation(self, res: Dict[str, Any]) -> str:
        """格式化 Observation 文本"""
        stdout = res.get("stdout", "").strip()
        stderr = res.get("stderr", "").strip()
        return_code = res.get("returncode")

        output = []
        if stdout:
            output.append(f"STDOUT:\n{stdout}")
        if stderr:
            output.append(f"STDERR:\n{stderr}")
        if return_code != 0:
            output.append(f"RETURNCODE: {return_code}")

        if not output:
             # 如果没有输出，至少返回一个成功的标记
             content = "Execution successful, but no output printed to STDOUT."
        else:
             content = "\n" + "\n".join(output)

        return f"Observation: {content}"

    def run_task(self, instruction: str, csv_path: str, max_steps: int = 6) -> Dict[str, Any]:
        """运行 ReAct Agent 任务"""
        scratchpad: List[Dict[str, Any]] = []

        if not os.path.exists(csv_path):
            return {"final": None, "scratchpad": scratchpad, "error": f"CSV文件不存在: {csv_path}"}

        # 将 instruction 和 CSV_PATH 组合成 Question 消息
        question_content = (
            f"Question: {instruction}\n"
            f"CSV_PATH: '{csv_path}'\n"
            "Proceed with your Thought and Action based on the protocol."
        )

        messages = [
            {"role": "user", "content": self.INSTRUCTION+'\n\n'+question_content},
        ]

        # -------------------------- 实现React Agent的迭代流程 ---------------------------
        # 首先调用模型并获得对应的反回，根据反馈的Action type来进行不同的处理
        # 如果获得最终答案，最终返回如下格式内容：return {"final": final_answer}
        
        for step in range(1, max_steps + 1):
            step_out = self._react_once(messages)  # 模型输出并解析

            scratchpad.append({
                "step": step,
                "action": step_out.get("action"),
                "thought": step_out.get("thought", ""),
                "raw": step_out.get("raw", ""),
            })

            # 1) final：直接返回
            if step_out.get("action") == "final":
                final_answer = (step_out.get("final_answer") or "").strip()
                return {"final": final_answer, "scratchpad": scratchpad}

            # 2) error：返回错误
            if step_out.get("action") == "error":
                return {"final": None, "scratchpad": scratchpad, "error": step_out.get("message", "unknown error")}

            # 3) python：执行代码并回填 Observation
            if step_out.get("action") == "python":
                code = step_out.get("code", "") or ""

        
                prelude = (
                    "import pandas as pd\n"
                    "import numpy as np\n"
                    "import os\n"
                    f"CSV_PATH = r'''{csv_path}'''\n"
                    "pd.set_option('display.max_columns', 200)\n"
                    "pd.set_option('display.width', 200)\n"
                    "\n"
                    "# --- Safety: forbid reading any csv except CSV_PATH ---\n"
                    "_orig_read_csv = pd.read_csv\n"
                    "def _safe_read_csv(path, *args, **kwargs):\n"
                    "    if isinstance(path, str) and os.path.abspath(path) != os.path.abspath(CSV_PATH):\n"
                    "        raise RuntimeError(f'ReadCSVBlocked: only CSV_PATH is allowed. got={path}')\n"
                    "    return _orig_read_csv(path, *args, **kwargs)\n"
                    "pd.read_csv = _safe_read_csv\n"
                    "\n"
                    "# --- Load df once ---\n"
                    "df = pd.read_csv(CSV_PATH)\n"
                )

                wrapped_code = prelude + "\n\n" + code

                res = self.run_code(wrapped_code, cwd=os.getcwd())  # 执行 python
                observation = self._format_observation(res)         # 格式化 Observation

                # 把模型原始输出追加到对话历史
                messages.append({"role": "assistant", "content": step_out.get("raw", "")})

                # 把 Observation 追加到对话历史，供下一轮使用
                messages.append({"role": "user", "content": observation})
                messages.append({"role": "user", "content": "If you can answer now, output EXACTLY in multi-line format:\nFinal Answer:\n@key[value]\n@key[value]\n... (one per line). No literal \\n."})


                continue  # 继续下一轮

            # 4) 其他未知 action：给一个 Observation 提示它纠正
            messages.append({"role": "assistant", "content": step_out.get("raw", "")})
            messages.append({"role": "user", "content": "Observation: STDERR:\nUnknownActionError. Use Action: python or output Final Answer: ..."})


        # ------------------------------------------------------------------------------

        # 如下代码只有在迭代到最大轮次时调用，即未能正确完成对应的任务
        print("[HALT] Reached maximum steps without a final answer.")
        return {"final": "达到最大步数仍未完成。", "scratchpad": scratchpad}

