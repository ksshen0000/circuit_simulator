FROM node:24 AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Empty VITE_API_URL makes the app call same-origin endpoints,
# which nginx reverse-proxies to the backend service.
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
