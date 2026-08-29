# Local development only.
#
# The frontend deploys to Vercel, which builds from source and does not use this
# file. It exists so `docker compose up` gives a complete stack on one machine.
#
# It is deliberately not a production image: it runs the dev server with hot
# reload. Do not deploy it. A production Next.js container would need
# `output: "standalone"`, a multi-stage build, and a non-root user — worth adding
# only if the frontend ever moves off Vercel.

FROM node:22-slim

# Dev server only; the real build happens on Vercel.
ENV NODE_ENV=development

WORKDIR /app

# package-lock.json is copied too so `npm ci` installs the resolved tree rather
# than re-resolving, keeping the container's dependencies identical to CI's.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
