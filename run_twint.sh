#!/bin/bash
query=$1
filename=$2
start=$3
end=$4

echo $start $end
mkdir -p "csvs/$filename"

start=$(date -d $start +%Y%m%d)
end=$(date -d $end +%Y%m%d)

truncate -s 0 "logs/$filename.txt"
cp header.csv "csvs/$filename.csv"

pgrep -f "run_twint.sh $query" | grep -v "$$" | xargs kill -9

while [[ $start -lt $end ]]
do
        bd=$(date -d"$end - 1 day" +"%Y-%m-%d")
        ed=$(date -d"$end" +"%Y-%m-%d")
        echo "Running $query for $bd"
        twint -s "$query" --csv --output "csvs/$filename/$bd.csv" --since "$bd" --until "$ed" --proxy-host tor >> "logs/$filename.txt"
        sed 1d "csvs/$filename/$bd.csv" >> "csvs/$filename.csv"
        end=$(date -d"$end - 1 day" +"%Y%m%d")
done