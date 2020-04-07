import React from "react";
import LoginForm from "../../components/login-form/login-form.component";
import SignupForm from "../../components/signup-form/signup-form.component";

const Auth = () => {
  return (
    <div className="container">
      <div className="row">
        <div className="col m6">
          <LoginForm />
        </div>
        <div className="col m5 offset-1">
          <SignupForm />
        </div>
      </div>
    </div>
  );
};

export default Auth;
