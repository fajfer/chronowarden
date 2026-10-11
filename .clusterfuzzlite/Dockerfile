# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

# OSS-Fuzz Python builder (Python 3.11 with atheris), pinned by digest
FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:756c7196c97d62a66c448e70bdeecce400e68ae2ee96d4393cb38d58ffca18d2

COPY . $SRC/chronowarden
WORKDIR $SRC/chronowarden
COPY .clusterfuzzlite/build.sh $SRC/
