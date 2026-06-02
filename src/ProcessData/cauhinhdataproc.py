gcloud dataproc clusters create bigdata-n9-ptit \
    --region=asia-southeast1 \
    --master-machine-type=n2-standard-8 \
    --master-boot-disk-size=100GB \
    --num-workers=3 \
    --worker-machine-type=n2-standard-8 \
    --worker-boot-disk-size=100GB \
    --image-version=2.1-debian11 \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --project=bigdataptit2026

gcloud dataproc jobs submit pyspark 03_silver_plus.py \
    --cluster=bigdata-n9-ptit \
    --region=asia-southeast1 \
    --project=bigdataptit2026