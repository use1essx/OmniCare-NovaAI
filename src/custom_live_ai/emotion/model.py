"""
ML model building and training for emotion classification
"""

import json
import glob
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Tuple, Optional
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score, confusion_matrix, classification_report
from sklearn.calibration import CalibratedClassifierCV
import joblib
import logging

from .config import EMOTIONS, RANDOM_SEED

logger = logging.getLogger(__name__)

# Try LightGBM first, fall back to XGBoost
try:
    from lightgbm import LGBMClassifier as BaseClassifier
    MODEL_TYPE = "LightGBM"
except ImportError:
    try:
        from xgboost import XGBClassifier as BaseClassifier
        MODEL_TYPE = "XGBoost"
    except ImportError:
        from sklearn.ensemble import RandomForestClassifier as BaseClassifier
        MODEL_TYPE = "RandomForest"
        logger.warning("Neither LightGBM nor XGBoost available, using RandomForest")


def build_model() -> Pipeline:
    """
    Build the emotion classification pipeline
    
    Returns:
        Scikit-learn Pipeline with scaler + classifier
    """
    if MODEL_TYPE == "LightGBM":
        classifier = BaseClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=RANDOM_SEED,
            verbose=-1,
            class_weight='balanced'
        )
    elif MODEL_TYPE == "XGBoost":
        classifier = BaseClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=RANDOM_SEED,
            verbosity=0
        )
    else:  # RandomForest
        classifier = BaseClassifier(
            n_estimators=100,
            max_depth=15,
            random_state=RANDOM_SEED,
            class_weight='balanced'
        )
    
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', classifier)
    ])
    
    return pipeline


def load_parquet_data(
    parquet_glob: str,
    label_strategy: str = "pseudo_faceapi",
    manual_labels_csv: Optional[str] = None
) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Load and prepare training data from parquet logs
    
    Args:
        parquet_glob: Glob pattern for parquet files
        label_strategy: "pseudo_faceapi" or "manual_csv"
        manual_labels_csv: Path to manual labels CSV (if using manual strategy)
        
    Returns:
        Tuple of (dataframe, feature_matrix, labels)
    """
    logger.info(f"Loading parquet files from {parquet_glob}")
    
    # Load all parquet files
    files = glob.glob(parquet_glob, recursive=True)
    if not files:
        raise ValueError(f"No parquet files found matching {parquet_glob}")
    
    logger.info(f"Found {len(files)} parquet files")
    dfs = [pd.read_parquet(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    
    logger.info(f"Loaded {len(df)} total records")
    
    # Parse JSON columns
    df['base_features_dict'] = df['base_features'].apply(json.loads)
    df['faceapi_emotions_dict'] = df['faceapi_emotions'].apply(
        lambda x: json.loads(x) if pd.notna(x) else None
    )
    
    # Generate labels based on strategy
    if label_strategy == "pseudo_faceapi":
        # Use argmax of face-api.js emotions as labels
        def get_pseudo_label(row):
            if row['faceapi_emotions_dict'] is None:
                return None
            emotions = row['faceapi_emotions_dict']
            if not emotions:
                return None
            return max(emotions, key=emotions.get)
        
        df['label'] = df.apply(get_pseudo_label, axis=1)
        df = df[df['label'].notna()]  # Keep only rows with labels
        
    elif label_strategy == "manual_csv":
        if not manual_labels_csv or not Path(manual_labels_csv).exists():
            raise ValueError(f"Manual labels CSV not found: {manual_labels_csv}")
        
        # Load manual labels
        manual_df = pd.read_csv(manual_labels_csv)
        # Merge on session_id and frame_idx
        df = df.merge(
            manual_df[['session_id', 'frame_idx', 'label']],
            on=['session_id', 'frame_idx'],
            how='inner'
        )
    else:
        raise ValueError(f"Unknown label strategy: {label_strategy}")
    
    logger.info(f"After labeling: {len(df)} records")
    
    # Extract feature vectors
    feature_names = sorted(df.iloc[0]['base_features_dict'].keys())
    X = np.array([
        [row['base_features_dict'].get(name, 0.0) for name in feature_names]
        for _, row in df.iterrows()
    ])
    
    # Extract labels
    y = df['label'].values
    
    logger.info(f"Feature matrix shape: {X.shape}")
    logger.info(f"Label distribution:\n{pd.Series(y).value_counts()}")
    
    return df, X, y


def train_model(
    parquet_glob: str,
    output_model_path: str,
    label_strategy: str = "pseudo_faceapi",
    manual_labels_csv: Optional[str] = None,
    val_strategy: str = "stratified_kfold",
    n_splits: int = 5
) -> Dict:
    """
    Train emotion classification model
    
    Args:
        parquet_glob: Glob pattern for parquet files
        output_model_path: Path to save trained model
        label_strategy: "pseudo_faceapi" or "manual_csv"
        manual_labels_csv: Path to manual labels CSV
        val_strategy: Validation strategy
        n_splits: Number of cross-validation splits
        
    Returns:
        Training report dictionary
    """
    logger.info("=" * 60)
    logger.info(f"Training emotion model with {MODEL_TYPE}")
    logger.info("=" * 60)
    
    # Load data
    df, X, y = load_parquet_data(parquet_glob, label_strategy, manual_labels_csv)
    
    # Build model
    base_pipeline = build_model()
    
    # Add probability calibration
    logger.info("Building calibrated classifier...")
    model = CalibratedClassifierCV(
        base_pipeline,
        method='sigmoid',
        cv=min(3, n_splits),
        n_jobs=-1
    )
    
    # Cross-validation
    logger.info(f"Running {n_splits}-fold cross-validation...")
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_SEED)
    
    cv_scores = []
    cv_reports = []
    
    for fold, (train_idx, val_idx) in enumerate(cv.split(X, y)):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]
        
        # Train
        model.fit(X_train, y_train)
        
        # Predict
        y_pred = model.predict(X_val)
        
        # Metrics
        f1_macro = f1_score(y_val, y_pred, average='macro')
        cv_scores.append(f1_macro)
        
        report = classification_report(y_val, y_pred, output_dict=True)
        cv_reports.append(report)
        
        logger.info(f"Fold {fold + 1}/{n_splits}: Macro F1 = {f1_macro:.4f}")
    
    avg_f1 = np.mean(cv_scores)
    std_f1 = np.std(cv_scores)
    logger.info(f"\nCross-validation Macro F1: {avg_f1:.4f} ± {std_f1:.4f}")
    
    # Train final model on all data
    logger.info("Training final model on all data...")
    model.fit(X, y)
    
    # Final predictions for confusion matrix
    y_pred_final = model.predict(X)
    cm = confusion_matrix(y, y_pred_final, labels=EMOTIONS)
    
    # Save model
    output_path = Path(output_model_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    logger.info(f"Model saved to {output_path}")
    
    # Generate report
    report = {
        "model_type": MODEL_TYPE,
        "label_strategy": label_strategy,
        "n_samples": len(df),
        "n_features": X.shape[1],
        "cv_macro_f1_mean": float(avg_f1),
        "cv_macro_f1_std": float(std_f1),
        "confusion_matrix": cm.tolist(),
        "emotion_labels": EMOTIONS,
        "per_class_metrics": classification_report(y, y_pred_final, output_dict=True)
    }
    
    logger.info("\n" + "=" * 60)
    logger.info("Training complete!")
    logger.info(f"Macro F1: {avg_f1:.4f} ± {std_f1:.4f}")
    logger.info("=" * 60)
    
    return report

