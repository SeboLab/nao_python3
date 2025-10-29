# NAO Python3 

This repository contains the **`nao_demo.py`** script, demonstrating a simplified NAO interaction with a user from Experiment 1 in *The Impact of a Robot’s Agreement (or Disagreement) on Human-Human Interpersonal Closeness in a Two-Person Decision-Making Task*. This code is written in Python3, and NAO's actions are controlled by qi library.

---

## How to run `nao_demo.py`?
- On an Ubuntu laptop, git clone this repo to your desired location
- cd into this repo, and create a `secret.csv` (which must include a column named `api_key`, with the actual API key listed in the row below the header)
- If `qi` library is not installed, on the terminal run: `pip install qi`
- On the terminal, run: `python3 nao_demo.py <NAO_IP_Address> <USER_NAME>`
- Follow the menu displayed on the terminal, select one of the six modes:

| Code | Description |
|------|--------------|
| `p`  | Positive feedback using ChatGPT |
| `n`  | Negative feedback using ChatGPT |
| `m`  | Alternating positive/negative feedback using ChatGPT |
| `sp` | Scripted positive feedback |
| `sn` | Scripted negative feedback |
| `sm` | Scripted alternating positive/negative feedback |

---

## Citation

If you use this code or build upon this work in your research, please cite the following publication:

```bibtex
@article{lin2025impact,
  title={The Impact of a Robot’s Agreement (or Disagreement) on Human-Human Interpersonal Closeness in a Two-Person Decision-Making Task},
  author={Lin, Ting-Han and Kopelman, Yuval Rubin and Busse, Madeline and Sebo, Sarah and Erel, Hadas},
  journal={Computers in Human Behavior},
  pages={108807},
  year={2025},
  publisher={Elsevier}
}

---

## Notes

This repo is updated on 10/28/2025. If you have any questions, please reach out to Ting-Han (Timmy) Lin (tinghan@uchicago.edu) or Jingyu Chen (jchen68@uchicago.edu).
