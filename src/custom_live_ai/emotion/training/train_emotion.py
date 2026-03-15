"""
CLI script for training emotion classification model
"""

import argparse
import json
import logging
from pathlib import Path

from ..model import train_model
from ..config import MODEL_PATH, TRAINING_REPORT_PATH

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Train emotion classification model from parquet logs'
    )
    
    parser.add_argument(
        '--data-glob',
        type=str,
        default='./data/logs/*/*/*/*.parquet',
        help='Glob pattern for parquet log files'
    )
    
    parser.add_argument(
        '--out',
        type=str,
        default=MODEL_PATH,
        help='Output path for trained model'
    )
    
    parser.add_argument(
        '--label-strategy',
        type=str,
        choices=['pseudo_faceapi', 'manual_csv'],
        default='pseudo_faceapi',
        help='Strategy for generating labels'
    )
    
    parser.add_argument(
        '--labels-csv',
        type=str,
        default=None,
        help='Path to manual labels CSV (required if label-strategy=manual_csv)'
    )
    
    parser.add_argument(
        '--n-splits',
        type=int,
        default=5,
        help='Number of cross-validation splits'
    )
    
    parser.add_argument(
        '--report',
        type=str,
        default=TRAINING_REPORT_PATH,
        help='Output path for training report JSON'
    )
    
    args = parser.parse_args()
    
    logger.info("Starting emotion model training")
    logger.info(f"Data glob: {args.data_glob}")
    logger.info(f"Label strategy: {args.label_strategy}")
    logger.info(f"Output model: {args.out}")
    
    # Validate args
    if args.label_strategy == 'manual_csv' and not args.labels_csv:
        parser.error("--labels-csv required when using manual_csv label strategy")
    
    # Train model
    try:
        report = train_model(
            parquet_glob=args.data_glob,
            output_model_path=args.out,
            label_strategy=args.label_strategy,
            manual_labels_csv=args.labels_csv,
            val_strategy='stratified_kfold',
            n_splits=args.n_splits
        )
        
        # Save report
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Training report saved to {report_path}")
        
        # Print summary
        print("\n" + "=" * 60)
        print("TRAINING SUMMARY")
        print("=" * 60)
        print(f"Model type: {report['model_type']}")
        print(f"Samples: {report['n_samples']}")
        print(f"Features: {report['n_features']}")
        print(f"CV Macro F1: {report['cv_macro_f1_mean']:.4f} ± {report['cv_macro_f1_std']:.4f}")
        print("\nPer-class F1 scores:")
        for emotion, metrics in report['per_class_metrics'].items():
            if isinstance(metrics, dict) and 'f1-score' in metrics:
                print(f"  {emotion:12s}: {metrics['f1-score']:.4f}")
        print("=" * 60)
        
        logger.info("Training completed successfully!")
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


if __name__ == '__main__':
    main()

