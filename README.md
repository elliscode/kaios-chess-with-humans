# KaiOS Chess with humans

Making a chess game for KaiOS to play with other humans, as there are no offerings on the KaiStore that allow playing chess with other humans.

## Backend

The backend runs on AWS. It uses AWS DynamoDB database for storage, AWS Lambda for the API, and AWS API Gateway to connect the API to the internet.

## Frontend

TODO

## Website

The website is a CloudFront distribution pointing to an S3 bucket, which talks to the backend.