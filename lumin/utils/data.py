import numpy as np
from typing import Optional, Union
import pandas as pd
from fastprogress import progress_bar

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

from ..nn.data.fold_yielder import FoldYielder
from ..optimisation.features import get_rf_feat_importance
from .statistics import uncert_round


def _check_val_set_fy(train:FoldYielder, val:FoldYielder, test:Optional[FoldYielder]=None, n_folds:Optional[int]=None) -> None:
    n = min(train.n_folds, val.n_folds)
    if test is not None: n = min(n, test.n_folds)
    if n_folds is None:  n = min(n, n_folds)
    train_feats = None
        
    samples = {'train': train} if test is None else {'train': train, 'test': test}
    for sample in samples:
        aucs = []
        fi = pd.DataFrame()
        for fold_id in progress_bar(range(n_folds)):
            df_0 = samples[sample].get_df(pred_name='None', inc_inputs=True, deprocess=True, fold_id=fold_id, verbose=False)
            df_1 = val.get_df(pred_name='None', inc_inputs=True, deprocess=True, fold_id=fold_id, verbose=False)
            df_0['gen_target'] = 0
            df_1['gen_target'] = 1
            df_0['gen_weight'] = 1/len(df_0)
            df_1['gen_weight'] = 1/len(df_1)

            df = df_0.append(df_1, ignore_index=True).sample(frac=1)
            df_trn, df_val = df[:len(df)//2], df[len(df)//2:]
            if train_feats is None: train_feats = [f for f in df_trn.columns if 'gen_' not in f]

            m = RandomForestClassifier(n_estimators=40, min_samples_leaf=25, n_jobs=-1)
            df_trn.replace([np.inf, -np.inf], np.nan, inplace=True)
            m.fit(df_trn[train_feats], df_trn['gen_target'], df_trn['gen_weight'])
            aucs.append(roc_auc_score(df_val['gen_target'], m.predict(df_val[train_feats]), sample_weight=df_val['gen_weight']))
            fi = fi.append(get_rf_feat_importance(m, df_val[train_feats], df_val['gen_target'], df_val['gen_weight']), ignore_index=True)

        mean = uncert_round(np.mean(aucs), np.std(aucs, ddof=1)/np.sqrt(len(aucs)))
        print(f"\nAUC for {sample}-validation discrimination = {mean[0]}±{mean[1]}")
        print("Top 10 most important features are:")
        mean_fi = pd.DataFrame()
        mean_fi['Importance'] = fi['Importance'].groupby(fi['Feature']).mean()
        mean_fi['Uncertainty'] = fi['Importance'].groupby(fi['Feature']).std()/np.sqrt(n)
        mean_fi.sort_values(['Importance'], inplace=True, ascending=False)
        mean_fi.reset_index(inplace=True)
        print(mean_fi[:min(10, len(mean_fi))])


def _check_val_set_np(train:Union[pd.DataFrame,np.ndarray], val:Union[pd.DataFrame,np.ndarray], test:Optional[Union[pd.DataFrame,np.ndarray]]=None) -> None:
    if not isinstance(train, pd.DataFrame): train = pd.DataFrame(train)
    if not isinstance(val, pd.DataFrame): val = pd.DataFrame(val)
    if test is not None and not isinstance(test, pd.DataFrame): test = pd.DataFrame(test)
    train_feats = None    

    samples = {'train': train} if test is None else {'train': train, 'test': test}
    for sample in samples:
        df_0 = samples[sample]
        df_1 = val
        df_0['gen_target'] = 0
        df_1['gen_target'] = 1
        df_0['gen_weight'] = 1/len(df_0)
        df_1['gen_weight'] = 1/len(df_1)

        df = df_0.append(df_1, ignore_index=True).sample(frac=1)
        df_trn, df_val = df[:len(df)//2], df[len(df)//2:]
        if train_feats is None: train_feats = [f for f in df_trn.columns if 'gen_' not in f]

        m = RandomForestClassifier(n_estimators=40, min_samples_leaf=25, n_jobs=-1)
        m.fit(df_trn[train_feats], df_trn['gen_target'], df_trn['gen_weight'])
        auc = roc_auc_score(df_val['gen_target'], m.predict(df_val[train_feats]), sample_weight=df_val['gen_weight'])
        fi = get_rf_feat_importance(m, df_val[train_feats], df_val['gen_target'], df_val['gen_weight']).sort_values(['Importance'], ascending=False).reset_index()
        print(f"\nAUC for {sample}-validation discrimination = {auc}")
        print("Top 10 most important features are:")
        print(fi[:min(10, len(fi))])


def check_val_set(train:Union[pd.DataFrame,np.ndarray,FoldYielder], val:Union[pd.DataFrame,np.ndarray,FoldYielder], test:Optional[Union[pd.DataFrame,np.ndarray,FoldYielder]]=None,
                  n_folds:Optional[int]=None) -> None:
    if isinstance(train, FoldYielder): _check_val_set_fy(train, val, test, n_folds)
    if isinstance(train, pd.DataFrame) or isinstance(train, np.ndarray): _check_val_set_np(train, val, test)
