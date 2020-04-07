import React, { Component } from "react";
import FormInput from "../form-input/form-input.component";
import CustomButton from "../custom-button/custom-button.component";

class LoginForm extends Component {
  state = {
    email: "",
    password: "",
  };

  handleChange = ({ target }) => {
    const name = target.name;
    const value = target.value;
    this.setState({ [name]: value });
  };
  handleSubmit = (e) => {
    e.preventDefault();
    console.log(this.state);
  };
  render() {
    return (
      <form onSubmit={this.handleSubmit} className="white">
        <h5 className="grey-text text-darken-3">Sign In</h5>
        <FormInput
          name="email"
          title="Email"
          type="email"
          value={this.state.email}
          handleChange={this.handleChange}
        />
        <FormInput
          name="password"
          title="Password"
          type="password"
          value={this.state.password}
          handleChange={this.handleChange}
        />
        <CustomButton title="login" />
      </form>
    );
  }
}

export default LoginForm;
