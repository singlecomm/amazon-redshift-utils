#!/usr/bin/env bash

CONTEXT=${1:-}
TAG=${2:-${TAG}}

if [[ ${CONTEXT} == 'prod' ]]; then
    BRANCH='master'
else
    BRANCH="${CONTEXT}"
fi

if [ -d "kubernetes-config-${CONTEXT}" ]; then
  rm -rf "kubernetes-config-${CONTEXT}"
fi

git clone git@github.com:singlecomm/kubernetes-config.git -b "${BRANCH}" "kubernetes-config-${CONTEXT}"
sed -i "s/singlecomm\\/amazon-redshift-utils:v[0-9]\\+.[0-9]\\+.[0-9]\\+/singlecomm\\/amazon-redshift-utils:$TAG/" kubernetes-config-${CONTEXT}/${CONTEXT}-coral/cronjobs/analyze-vacuum-redshift.yml
kubectl --context="${CONTEXT}" --namespace="${CONTEXT}-coral" apply -f kubernetes-config-${CONTEXT}/${CONTEXT}-coral/cronjobs/analyze-vacuum-redshift.yml
cd kubernetes-config-${CONTEXT}
git add ${CONTEXT}-coral/cronjobs/analyze-vacuum-redshift.yml
git commit -m "chore(release): Amazon Redshift Utils Version $TAG"
git push origin ${BRANCH}
cd ..
rm -rf "kubernetes-config-${CONTEXT}"
