#!/bin/bash
if [ "$ENV" = "dev" ]; then
    FUNCTION_SUFFIX="-dev"
else
    FUNCTION_SUFFIX=""
fi

if $lambda; then
    cd lambda/
    cp -r $(pipenv --venv)/lib/python3.14/site-packages/chess .
    TIMESTAMP=$(date +%s)
    zip -vr ../lambda-release-${ENV}-${TIMESTAMP}.zip . -x "*.DS_Store" -x "*.test.py" -x "*__pycache__/*"
    rm -r chess/
    cd ../
    aws lambda update-function-code --function-name=chess-with-humans-api${FUNCTION_SUFFIX} --zip-file=fileb://lambda-release-${ENV}-${TIMESTAMP}.zip --no-cli-pager
fi