import random
from collections import namedtuple
from typing import Dict
import torch
import logging

from dataset.filed_base import Field
from Utils.file_utils import read_json, read_fenci_json, read_fenci_z2e_json

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)
Batch = namedtuple("Batch",
                   ['Gsens', 'Gcpts', 'Gsens_adjs', 'dec_inputs', 'batch_size', 'probs',
                    'idxes'])
Example = namedtuple("Example",
                     ['Gsen_vertex_features', 'Gcpt_vertex_features', 'Gsen_adj_martix', 'tgt'])


class TranslationDataset(object):
    def __init__(self,
                 src_path: str,
                 tgt_path: str,
                 opt,
                 device: torch.device,
                 train: bool,
                 fields: Dict[str, Field]):

        self.batch_size = opt.batch_size
        self.emd_type = opt.emd_type
        self.max_swords = opt.max_swords
        self.train = train
        self.device = device
        self.fields = fields
        examples = []
        if (opt.cpt_type == "small"):
            for Gsen_vertex_features, Gcpt_vertex_features, Gsen_adj_martix, Gcpt_adj_martix, summary in read_fenci_json(
                    src_path):
                concept = []
                for cpt in Gcpt_vertex_features:
                    concept = concept + cpt
                examples.append(
                    Example(Gsen_vertex_features, concept, Gsen_adj_martix,
                            summary))
        elif (opt.cpt_type == "big"):
            for Gsen_vertex_features, Gcpt_vertex_features, Gsen_adj_martix, summary in read_fenci_z2e_json(
                    src_path):
                concept = []
                for cpt in Gcpt_vertex_features:
                    concept = concept + cpt
                examples.append(
                    Example(Gsen_vertex_features, concept, Gsen_adj_martix,
                            summary))
        examples, self.seed = self.sort(examples)  
        self.num_examples = len(examples)
        self.batches = list(batch(examples, self.batch_size)) 

    def __iter__(self):  
        while True:
            if self.train:
                random.shuffle(self.batches)
            for minibatch in self.batches:  # 输入为 {'src': src_field, 'tgt': tgt_field}
                if (self.emd_type == 2):
                    Gsen_feature_padded, Gsen_adj_padded, Gcpt_feature_padded, Gcpt_adj_padded = self.fields[
                        "src"].process(
                        [x for x in minibatch], self.device, self.max_swords, prc_type=1)
                    probs, idxes = self.fields["src"].prb_idx([x.concepts for x in minibatch], self.device)
                if (self.emd_type == 1):
                    Gsen_feature_padded, Gsen_adj_padded, Gcpt_feature_padded,  probs, idxes = \
                        self.fields[
                            "src"].process(
                            [x for x in minibatch], self.device, self.max_swords, prc_type=4)
                dec_inputs = self.fields["tgt"].process([x.tgt for x in minibatch], self.device, self.max_swords,prc_type=2)
                # dec_outputs = self.fields["tgt"].process([x.tgt for x in minibatch], self.device, self.max_swords,
                #                                          self.max_cwords, prc_type=3)
                yield Batch(Gsens=Gsen_feature_padded, Gcpts=Gcpt_feature_padded, Gsens_adjs=Gsen_adj_padded, dec_inputs=dec_inputs,
                            batch_size=len(minibatch), probs=probs, idxes=idxes)
            if not self.train:  
                break

    def sort(self, examples):
        sort_key = lambda ex: (len(ex.Gsen_vertex_features), len(ex.Gcpt_vertex_features), len(ex.tgt))
        seed = sorted(range(len(examples)), key=lambda idx: sort_key(examples[idx]))
        return sorted(examples, key=sort_key), seed


def batch(data, batch_size):
    minibatch, cur_len = [], 0
    for ex in data:
        minibatch.append(ex)
        cur_len = max(cur_len, len(ex.Gsen_vertex_features), len(ex.Gcpt_vertex_features), len(ex.tgt))
        # print(len(ex.Gsen_vertex_features), len(ex.Gcpt_vertex_features), len(ex.tgt), '->', cur_len)
        if cur_len > batch_size:
            yield minibatch
            minibatch, cur_len = [], max(len(ex.Gsen_vertex_features), len(ex.Gcpt_vertex_features), len(ex.tgt))
        elif cur_len * len(minibatch) > batch_size:  
            yield minibatch[:-1]
            minibatch, cur_len = [ex], max(len(ex.Gsen_vertex_features), len(ex.Gcpt_vertex_features), len(ex.tgt))
    if minibatch:
        yield minibatch
