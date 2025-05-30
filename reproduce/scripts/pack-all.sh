#!/bin/bash

PROJECT_ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/../../

# configurations
min_div_rounds=1
max_div_rounds=50
binary="ls"

# create a build dir if not exist
if ! test -d $PROJECT_ROOT/reproduce/build; then
    mkdir $PROJECT_ROOT/reproduce/build
fi

pack_binary() {
    local circuit="$1"
    local dir="$2"
    local output_dir="$PROJECT_ROOT/reproduce/build/$binary-$circuit"

    # create a dir for the circuit if not exist
    if ! test -d $output_dir; then
        mkdir $output_dir
    fi

    # run packers with different transient window sizes
    for div_round in $(seq $min_div_rounds $max_div_rounds); do        
        name="upx-${circuit}-${div_round}.elf"
        packer=$dir/$circuit/$name
        output=$output_dir/$binary-$circuit-$div_round.elf

        # ensure the packer exists
        if [ ! -f $packer ]; then
            echo "Packer ${name} does not exist!"
            echo "Please compile the packers before running this script."
            exit 1
        fi

        # delete existing output files
        if [ -f $output ]; then
            rm $output
        fi

        # run the packer
        $packer $PROJECT_ROOT/reproduce/$binary -o $output_dir/$binary-$circuit-$div_round.elf > /dev/null

        echo -ne "Progress ($circuit): ${div_round}/${max_div_rounds}\r"
    done
    echo -ne '\n'
}

pack_binary simon25_CTR $PROJECT_ROOT/UPFlexo/build
pack_binary simon32_CTR $PROJECT_ROOT/UPFlexo/build
pack_binary AES_CTR $PROJECT_ROOT/UPFlexo/build
