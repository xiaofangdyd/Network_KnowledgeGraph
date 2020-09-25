import numpy as np
import json
import pickle
import os


class KGDataset():
    def __init__(self, dataset, delimiter='\t', load_from_txt=True, load_dict=False):
        self.delimiter = delimiter
        self.dataset = dataset
        self.num_entity = 0
        self.num_relation = 0
        self.filter_node = {}
        if load_from_txt:
            self.data = self.read_data()
            print('processing data...')
            self.entity2idx, self.idx2entity = self.token_dict(label='entity')
            self.rel2idx, self.idx2rel = self.token_dict(label='relation')
            print('saving data to disk...')
            self.save_to_disk()
        else:
            print("Need to load data from disk! Use load_from_disk().")
            self.entity2idx = {}
            self.rel2idx = {}
            self.idx2entity = {}
            self.idx2rel = {}
        if load_dict:
            if not os.path.exists(f"./dataset/{self.dataset}/filter_node"):
                print("filter_node file not found!")
            else:
                self.filter_node = pickle.load(open(f"./dataset/{self.dataset}/filter_node", 'rb'))

    # 从原始数据集中加载数据
    def read_data(self):
        files = f"./dataset/{self.dataset}/triples.txt"
        data = np.loadtxt(files, dtype=np.str, delimiter=self.delimiter)
        print(f"Total samples number: {data.shape[0]}")
        return data

    # 构建实体和联系的 str <-> int 转换字典
    def list2dict(self, token_list):
        token2idx = dict([(token, num+2) for num, token in enumerate(token_list)])
        token2idx['OOV'] = int(0)
        token2idx[''] = int(1)
        idx2token = dict([(num+2, token) for num, token in enumerate(token_list)])
        idx2token[int(0)] = 'OOV'
        idx2token[int(1)] = ''
        return token2idx, idx2token

    # label可取entity、relation
    def token_dict(self, label):
        e1, rel, e2 = np.hsplit(self.data, 3)
        if label == 'entity':
            entity = np.vstack((e1, e2)).reshape((-1))
            entity = list(set(entity))
            self.num_entity = len(entity)
            token2idx, idx2token = self.list2dict(entity)
        elif label == 'relation':
            rel = rel.reshape((-1))
            rel = list(set(rel))
            self.num_relation = len(rel)
            token2idx, idx2token = self.list2dict(rel)
        else:
            print(f"dataset/dataloader.py function 'token_dict' got a wrong label: {label}")
            print('Expect label is entity or relation')
            exit(1)
        return token2idx, idx2token

    # 根据idx得到原始token， label可选entity或relation
    def get_token(self, idx, label):
        if label == 'relation':
            if idx in self.idx2rel.keys():
                return self.idx2rel[idx]
            else:
                return self.idx2rel[0]
        if label == 'entity':
            if idx in self.idx2entity.keys():
                return self.idx2entity[idx]
            else:
                return self.idx2entity[0]

    # 根据token得到idx， label可选entity或relation
    def get_idx(self, token, label):
        if label == 'relation':
            if token in self.rel2idx.keys():
                return self.rel2idx[token]
            else:
                return self.rel2idx['OOV']
        if label == 'entity':
            if token in self.entity2idx.keys():
                return self.entity2idx[token]
            else:
                return self.entity2idx['OOV']

    # 从本地存储中载入字典信息, 同时需要计算entity和relation的数量, 返回bool
    def load_from_disk(self, path='!'):
        print('loading data...')
        if path == '!':
            path = f"./dataset/{self.dataset}/dict_data"
        if not os.path.exists(path):
            print("no local disk file!")
            return False
        self.entity2idx, self.rel2idx, self.idx2entity, self.idx2rel = pickle.load(open(path, 'rb'))
        self.num_entity = len(self.entity2idx)
        self.num_relation = len(self.rel2idx)
        return True

    # 将字典信息储存到本地存储
    def save_to_disk(self, path='!'):
        if path == '!':
            path = f"./dataset/{self.dataset}/dict_data"
        pickle.dump([self.entity2idx, self.rel2idx, self.idx2entity, self.idx2rel], open(path, 'wb'))
        if self.filter_node:
            print(f"saving filter_node dict...")
            pickle.dump(self.filter_node, open(f"./dataset/{self.dataset}/filter_node", 'wb'))


class OriginDataset(KGDataset):
    def __init__(self, dataset, delimiter='\t', load_from_txt=True, load_dict=False):
        super().__init__(dataset, delimiter, load_from_txt=False, load_dict=load_dict)
        if load_from_txt:
            self.data = self.read_data()
            print('processing data...')
            self.entity2idx, self.idx2entity = self.token_dict(label='entity')
            self.rel2idx, self.idx2rel = self.token_dict(label='relation')
            print('saving data to disk...')
            self.save_to_disk()

    def read_data(self):
        data = np.zeros(shape=(1, 3))
        files = ['train.txt', 'valid.txt', 'test.txt']
        for p in files:
            tmp = np.loadtxt(f"./dataset/{self.dataset}/{p}", dtype=np.str, delimiter=self.delimiter)
            data = np.vstack((data, tmp))
        data = data[1:]
        print(f"Total samples number: {data.shape[0]}")
        return data

    # 将三元组（h, r, t）信息添加到self.filter_node中
    def add_filter_node(self, e1, rel, e2):
        if e1 not in self.filter_node.keys():
            triple_dict = {rel: []}
            triple_dict[rel].append(e2)
            self.filter_node[e1] = triple_dict
        else:
            if rel not in self.filter_node[e1].keys():
                self.filter_node[e1][rel] = []
                self.filter_node[e1][rel].append(e2)
            else:
                if e2 not in self.filter_node[e1][rel]:
                    self.filter_node[e1][rel].append(e2)

    # 生成训练集中已知节点的链接关系
    def generate_filter_node(self):
        train_data = np.loadtxt(f"./dataset/{self.dataset}/train.txt", dtype=np.str, delimiter=self.delimiter)
        for triple in train_data:
            e1, rel, e2 = np.hsplit(triple, 3)
            e1, rel, e2 = self.get_idx(e1[0], label='entity'), self.get_idx(rel[0], label='relation'), self.get_idx(e2[0], label='entity')
            # 因为知识图谱为无向图，所以三元组的两种链接方向都需要添加
            self.add_filter_node(e1, rel, e2)
            self.add_filter_node(e2, rel, e1)

    # 通过e1和rel，获取已知链接的节点列表
    def get_filter_node(self, e1, rel):
        if e1 not in self.filter_node.keys():
            return 'Wrong entity1!'
        elif rel not in self.filter_node[e1].keys():
            return 'Wrong relation!'
        else:
            return self.filter_node[e1][rel]
