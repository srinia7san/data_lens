'''
this file is to claucalte evaluation metrics fpr my retiever
'''

from dataclasses import dataclass
from typing import List,Set

@dataclass
class RetrievalMetrics:
    true_positive  : int
    false_positive : int
    false_negative : int

    ground_truth_tables: Set[str]
    retrieved_tables :Set[str]

    matched_tables:Set[str]
    missing_tables :Set[str]
    extra_tables:Set[str]

    precision : float
    recall :float
    f1_score : float

class RetrievalEvaluator:
    @staticmethod
    def evaluate(ground_truth:List[str],retrieved:List[str]) -> RetrievalMetrics:
        gt = set(ground_truth)
        rt = set(retrieved)

        matched = gt & rt
        extra = rt - gt
        missing = gt - rt

        tp = len(matched)
        fp = len(extra)
        fn = len(missing)

        # caluclting pecison
        precision =  (
            tp /(tp + fp)

            if (tp + fp) > 0 
            else 0
        )

        recall = (tp/
                  (tp+ fn)
                  if (tp + fn) > 0
                  else 0)

        if precision + recall == 0:
            f1 = 0
        else:
            f1 = (
                2 * precision * recall
                / (precision + recall)
            )

        return RetrievalMetrics(
            true_positive=tp,
            false_positive=fp,
            false_negative=fn,

            precision=precision,
            recall=recall,
            f1_score=f1,

            retrieved_tables=rt,
            ground_truth_tables = gt,


            matched_tables=matched,
            extra_tables=extra,
            missing_tables=missing)