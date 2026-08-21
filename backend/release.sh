#!/bin/bash

cd lambda/
cp -r ../.venv/lib/python3.14/site-packages/chess .
TIMESTAMP=$(date +%s)
zip -vr ../lambda-release-${TIMESTAMP}.zip . -x "*.DS_Store" -x "*.test.py" -x "*__pycache__/*"
rm -r chess/
cd ../
aws lambda update-function-code --function-name=chess-with-humans-api-dev --zip-file=fileb://lambda-release-${TIMESTAMP}.zip --no-cli-pager