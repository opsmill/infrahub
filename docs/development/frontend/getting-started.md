---
title: Getting set up
icon: rocket
order: 1000
---
# Getting set up with Frontend

!!!warning Before we start
Make sure [Infrahub Backend](../backend.md) is up and running. If not, in your terminal execute:

```shell
invoke demo.destroy demo.build demo.start demo.load-infra-schema demo.load-infra-data
```

!!!

Infrahub is built with React. Make sure you're running Node.js 20+ and NPM 9+, to verify do:

```shell
node --version
npm --version
```

## 1. Install dependencies

```shell
cd /frontend
npm install
```

## 2. Start a local server

```shell
npm start
```

To can access your local server at [http://localhost:8080/](http://localhost:8080/). If you are not familiar with Infrahub, learn by following our [tutorial](/tutorials/getting-started/).

## 3. Run all tests

### Unit tests

```sh
npm run test

# same with coverage
npm run test:coverage
```

### Integration tests

```sh
npm run cypress:run:component
```

### E2E tests

```sh
npm run test:e2e
```

All tests should succeed. For more information on testing, read [Running & Writing Tests](testing-guidelines.md).
