#! /bin/bash

NUM_PROCESSES=10

TOTAL_USERS=1000000
TOTAL_TWEETS=1000000

USER_BATCH=$((TOTAL_USERS / NUM_PROCESSES))
TWEETS_BATCH=$((TOTAL_TWEETS / NUM_PROCESSES))

for i in $(seq 0 $((NUM_PROCESSES-1))); do
    USER_ID_START=$((i * USER_BATCH))
    TWEET_ID_START=$((i * TWEETS_BATCH))
    
    echo "Launching process $i with user_id_start=$USER_ID_START and tweet_id_start=$TWEET_ID_START"

    python load_test_data.py --users $USER_BATCH --tweets $TWEETS_BATCH \
        --user_id_start $USER_ID_START --tweet_id_start $TWEET_ID_START &
    done

wait

echo "Fully done!"
