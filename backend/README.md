# setup

1. download the profanities list with this command

```
curl https://raw.githubusercontent.com/coffee-and-fun/google-profanity-words/refs/heads/main/data/en.txt > backend/lambda/chesswithhumans/bad_words.txt
```

2. create a lambda
3. run the `sh release.sh` script
4. set up an API gateway with an ANY method with proxy integration and set your lambda as the target of the lambda integration


# releasing

run `sh release.sh`
